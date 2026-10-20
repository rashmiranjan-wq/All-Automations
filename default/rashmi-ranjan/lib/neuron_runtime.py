"""Shared helpers for Databricks -> Neuron sheet-automation migrations.

Credentials come from Neuron pod env vars (navi-notebook-secrets), never from code.
"""

import json
import os
import re

import gspread
import pandas as pd
import requests
from gspread_dataframe import set_with_dataframe
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Same service account project as Databricks Automation Playground (352212).
_GSHEET_ENV_KEYS = (
    "NAVI_PLATFORM_GOOGLE_SHEETS_SA_JSON_352212",
    "NAVI_PLATFORM_TREZO_GSHEET_AUTOMATION_SA_JSON",
    "ADS_TRACKER_GSHEET_SA_KEY",
    "NAVI_PLATFORM_ADS_TRACKER_GSHEET_SA_KEY",
)

_SLACK_ENV_KEYS = (
    "NAVI_PLATFORM_SLACK_TOKEN_SELF_SERVE_AUTOMATIONS",
)


def load_service_account():
    for key in _GSHEET_ENV_KEYS:
        raw = os.environ.get(key)
        if raw:
            return json.loads(raw)
    raise RuntimeError(
        "No Google Sheets service account found in pod env. "
        f"Expected one of: {', '.join(_GSHEET_ENV_KEYS)}"
    )


def load_slack_token():
    for key in _SLACK_ENV_KEYS:
        token = os.environ.get(key)
        if token:
            return token
    return None


def _spark():
    try:
        return spark  # noqa: F821 — injected on some kernels
    except NameError:
        from pyspark.sql import SparkSession

        return SparkSession.builder.getOrCreate()


def get_sql_df(query):
    """Run SQL on the active Spark Connect session and return a pandas DataFrame."""
    return _spark().sql(query).toPandas()


def get_trino_df(query, retries=3, retry_delay_s=15):
    """Run SQL on Trino (Presto dialect) and return a pandas DataFrame."""
    import time
    import trino
    from trino.exceptions import Http503Error

    last_err = None
    for attempt in range(1, retries + 1):
        conn = trino.dbapi.connect(
            host="trino-tableau-prod.dp.navi-tech.in",
            port=443,
            user="databricks-user",
            catalog="awsdatacatalog",
            schema="default",
            http_scheme="https",
            client_tags=["databricks"],
        )
        try:
            cur = conn.cursor()
            cur.execute("SET SESSION join_distribution_type = 'PARTITIONED'")
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Http503Error as exc:
            last_err = exc
            conn.close()
            if attempt < retries:
                time.sleep(retry_delay_s)
                continue
            raise
        except Exception:
            conn.close()
            raise
    raise last_err


def make_unique_columns(columns):
    seen = {}
    unique_cols = []
    for col in columns:
        if col not in seen:
            seen[col] = 0
            unique_cols.append(col)
        else:
            seen[col] += 1
            unique_cols.append(f"{col} ({seen[col]})")
    return unique_cols


def _gid_from_gsheet_url(gsheet_url):
    match = re.search(r"[?&#]gid=(\d+)", gsheet_url or "")
    return match.group(1) if match else None


class GoogleSheetReader:
    def __init__(self, gsheet_url, service_account=None):
        self.gsheet_url = gsheet_url
        self.gsheet_key = gsheet_url.split("/")[5]
        sa = service_account or load_service_account()
        if isinstance(sa, str):
            sa = json.loads(sa)
        self.service_account = sa
        self.gc = gspread.service_account_from_dict(sa)

    def get_gsheet(self):
        return self.gc.open_by_key(self.gsheet_key)

    def get_sheet(self, worksheet_name):
        try:
            return self.get_gsheet().worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return self.get_gsheet().add_worksheet(title=worksheet_name, rows="200", cols="20")

    def get_excel_cell(self, row_num, col_num):
        col_str = ""
        div = col_num
        while div:
            modulo = (div - 1) % 26
            col_str = chr(65 + modulo) + col_str
            div = (div - 1) // 26
        return col_str + str(row_num)

    def clear_sheets(self, sheetname, start_row, start_column, end_row=None, end_column=None):
        sheet = self.get_sheet(sheetname)
        data_range = sheet.get_all_values()
        num_rows = end_row if end_row is not None else len(data_range)
        num_cols = end_column if end_column is not None else len(data_range[0])
        range_ = "{start}:{end}".format(
            start=self.get_excel_cell(start_row, start_column),
            end=self.get_excel_cell(num_rows, num_cols),
        )
        sheet.batch_clear([range_])

    def set_df_in_sheets(self, worksheet_name, df, include_headers=True, row=1, col=1):
        worksheet = self.get_sheet(worksheet_name)
        set_with_dataframe(worksheet, df, row, col, include_column_header=include_headers)
        print(f"Data has been set to {worksheet_name}")

    def download_google_sheet_as_image(self, destination_folder, sheet_name=None, options=None):
        from google.oauth2 import service_account as sa_mod
        from googleapiclient.discovery import build
        from PIL import Image
        import fitz

        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = sa_mod.Credentials.from_service_account_info(self.service_account, scopes=scopes)
        base_url = f"https://docs.google.com/spreadsheets/d/{self.gsheet_key}/export?format=pdf"
        default_options = {"portrait": False, "gridlines": False, "printtitle": False, "scale": 4}
        if options:
            default_options.update(options)
        params = {
            "gid": "",
            "portrait": str(default_options["portrait"]).lower(),
            "gridlines": str(default_options["gridlines"]).lower(),
            "printtitle": str(default_options["printtitle"]).lower(),
            "scale": str(default_options["scale"]),
        }
        if sheet_name:
            service = build("sheets", "v4", credentials=creds)
            meta = service.spreadsheets().get(spreadsheetId=self.gsheet_key).execute()
            for sheet in meta.get("sheets", []):
                if sheet["properties"]["title"] == sheet_name:
                    params["gid"] = str(sheet["properties"]["sheetId"])
                    break
        if not params["gid"]:
            params["gid"] = _gid_from_gsheet_url(self.gsheet_url) or ""
        if not params["gid"]:
            raise RuntimeError(
                f"Worksheet '{sheet_name}' not found and no gid in spreadsheet URL"
            )
        export_url = base_url + "&" + "&".join(f"{k}={v}" for k, v in params.items())
        response = requests.get(export_url, headers={"Authorization": f"Bearer {creds.token}"})
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to download sheet PDF: HTTP {response.status_code} "
                f"(gid={params['gid']}, sheet={sheet_name!r})"
            )
        pdf_filename = os.path.join(destination_folder, f"{sheet_name or 'Google_Sheet'}.pdf")
        with open(pdf_filename, "wb") as pdf_file:
            pdf_file.write(response.content)
        doc = fitz.open(pdf_filename)
        image_path = None
        for page_num in range(len(doc)):
            pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            gray = img.convert("L")
            bbox = gray.getbbox()
            if bbox:
                img = img.crop(bbox)
            image_path = pdf_filename.replace(".pdf", f"_page{page_num + 1}.png")
            img.save(image_path, "PNG")
        os.remove(pdf_filename)
        return image_path


class SlackReportsTrigger:
    def __init__(self, slack_token=None):
        self.slack_token = slack_token or load_slack_token()
        if not self.slack_token:
            raise RuntimeError("No Slack token in pod env")
        self.client = WebClient(token=self.slack_token, timeout=60)

    _CHANNEL_NAME_TO_ID = {
        "procex-daily-updates": "C07K5MBQVDW",
        "procex-internal-metrics": "C08CXD3QVLH",
    }

    def _resolve_channel_id(self, channel):
        channel_str = str(channel).strip()
        if channel_str.startswith("C") and len(channel_str) >= 9:
            return channel_str
        name = channel_str.lstrip("#")
        if name in self._CHANNEL_NAME_TO_ID:
            return self._CHANNEL_NAME_TO_ID[name]
        raise ValueError(f"Slack channel not found: {channel}")

    def send_file_to_slack(self, channel, file_path, title, user_mentions=None, message=None):
        channel_id = self._resolve_channel_id(channel)
        mention_text = "CC: " + " ".join(f"<@{u}>" for u in user_mentions) if user_mentions else ""
        initial_comment = None
        if message or mention_text:
            initial_comment = f"{message or ''}\n{mention_text}".strip()
        ext = os.path.splitext(file_path)[1].lstrip(".")
        with open(file_path, "rb") as f:
            content = f.read()
        try:
            self.client.files_upload_v2(
                channel=channel_id,
                filename=f"{title}.{ext}",
                title=title,
                content=content,
                initial_comment=initial_comment,
            )
            print("File uploaded to Slack")
        except ValueError as exc:
            print(f"Slack upload error: {exc}")
        except SlackApiError as exc:
            print(f"Slack upload error: {exc.response.get('error', exc)}")
