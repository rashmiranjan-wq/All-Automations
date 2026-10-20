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
    "project_id": "apex-slack-card-0909154314",
}

dag = DAG(
    tags=['neuron', 'owner:rashmi-ranjan', 'pipeline:apex-slack-card'],
    max_active_runs=1,
    dag_id='neuron_rashmi-ranjan_apex_slack_card',
    default_args=args,
    schedule_interval='0 16 * * *',
    start_date=pendulum.today("UTC").add(days=-1),
    catchup=False,
    description="""
Created with Elyra 4.1.1 pipeline editor using `default/rashmi-ranjan/pipeline/apex-slack-card.pipeline`.
    """,
    is_paused_upon_creation=False,
)


# Operator source: {"catalog_type": "local-file-catalog", "component_ref": {"base_dir": "/opt/conda/share/jupyter/components/airflow", "path": "run_notebook_operator.py"}}

op_d129ec0f_0765_5837_a924_896253325962 = RunNotebookOperator(
    task_id="RunNotebookOperator",
    notebook_path="default/rashmi-ranjan/notebooks/apex_slack_card.ipynb",
    notebook_image="DBR 15.4 \u2014 SMALL (Spark Connect)",
    dedicated_cluster=False,
    cpu_request="500m",
    mem_request="2Gi",
    env_vars={},
    executor_config={},
    dag=dag,
)
