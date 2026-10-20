import os as _os
import sys as _sys
_NEURON_REPO_ROOT = _os.path.abspath(_os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "..", "..", ".."
))
if _NEURON_REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _NEURON_REPO_ROOT)

from run_notebook_operator import RunNotebookOperator
from airflow import DAG

import pendulum

args = {
    "project_id": "vkyc-slack-card-new-0909154005",
}

dag = DAG(
    tags=['neuron', 'owner:rashmi-ranjan', 'pipeline:vkyc-slack-card-new'],
    max_active_runs=1,
    dag_id='neuron_rashmi-ranjan_vkyc_slack_card_new',
    default_args=args,
    schedule_interval='0 16 * * *',
    start_date=pendulum.today("UTC").add(days=-1),
    catchup=False,
    description="""
Created with Elyra 4.1.1 pipeline editor using `default/rashmi-ranjan/pipeline/vkyc-slack-card-new.pipeline`.
    """,
    is_paused_upon_creation=False,
)


# Operator source: {"catalog_type": "local-file-catalog", "component_ref": {"base_dir": "/opt/conda/share/jupyter/components/airflow", "path": "run_notebook_operator.py"}}

op_fd35ec56_24e9_5566_89d9_e65043810413 = RunNotebookOperator(
    task_id="RunNotebookOperator",
    notebook_path="default/rashmi-ranjan/notebooks/vkyc_slack_card_new.ipynb",
    notebook_image="DBR 15.4 \u2014 SMALL (Spark Connect)",
    dedicated_cluster=False,
    cpu_request="500m",
    mem_request="2Gi",
    env_vars={},
    executor_config={},
    dag=dag,
)
