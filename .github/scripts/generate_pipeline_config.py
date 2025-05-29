""" 
This script prompts the pipeline creator (you) for configuration details
based on the pipeline type and generates the appropriate pipeline config YAML.
Output goes to `dag_configs/` and `github_mappings/`.

Intended for Tier 2 users: data engineers or power users.
"""

import os
import yaml
from pathlib import Path

def get_input(prompt, optional=False, default=None):
    val = input(prompt + (' (optional): ' if optional else ': '))
    if optional and not val:
        return default
    return val.strip()

def generate_config():
    pipeline_type = get_input("Enter pipeline type (s3_to_snowflake, snowflake_to_email, api_to_snowflake, ftp_to_snowflake)")
    pipeline_name = get_input("Enter pipeline name (used as DAG name and folder prefix)")

    config = {
        "pipeline_name": pipeline_name,
        "schedule": "@daily",  # default
        "tasks": []
    }

    if pipeline_type == "s3_to_snowflake":
        sql_path = get_input("Path to CREATE TABLE SQL file")
        with open(sql_path) as f:
            sql = f.read()
        config["tasks"] = [
            {"type": "extract_s3", "bucket": "{{ auto }}", "prefix": f"{pipeline_name}/"},
            {"type": "load_to_snowflake", "table": pipeline_name, "stage": "{{ auto }}"},
            {"type": "archive_s3", "source": f"s3://{{ auto }}/{pipeline_name}/", "archive": f"s3://{{ auto }}/archive/{pipeline_name}/"}
        ]

    elif pipeline_type == "snowflake_to_email":
        config["schedule"] = get_input("Enter report schedule (cron or text)", optional=True, default="@daily")
        config["tasks"] = [
            {"type": "extract_sql", "sql": get_input("Enter SELECT SQL for report")},
            {"type": "save_excel", "output_path": f"s3://reports/{pipeline_name}.xlsx"},
            {"type": "send_email", "to": get_input("Enter recipient email"), "subject": f"Report: {pipeline_name}", "attachment_path": f"s3://reports/{pipeline_name}.xlsx"}
        ]

    elif pipeline_type == "api_to_snowflake":
        config["schedule"] = get_input("Enter API schedule (e.g. cron: 0 6 * * *)")
        config["tasks"] = [
            {"type": "extract_api", "endpoint": get_input("API URL"), "headers": {"Authorization": get_input("Authorization token")}},
            {"type": "save_to_s3", "output_path": f"s3://raw/{pipeline_name}/{{{{ ds_nodash }}}}.json"},
            {"type": "load_to_snowflake", "stage": "{{ auto }}", "table": get_input("Target Snowflake table")},
            {"type": "archive_s3", "source": f"s3://raw/{pipeline_name}/{{{{ ds_nodash }}}}.json", "archive": f"s3://archive/{pipeline_name}/"}
        ]

    elif pipeline_type == "ftp_to_snowflake":
        config["tasks"] = [
            {"type": "extract_ftp", 
             "host": get_input("FTP host"), 
             "port": 21, 
             "username": get_input("FTP username"), 
             "password": get_input("FTP password"), 
             "remote_path": get_input("Remote file path"),
             "local_path": f"/tmp/{pipeline_name}.csv"},
            {"type": "load_to_s3", "input_path": f"/tmp/{pipeline_name}.csv", "output_path": f"s3://{{ auto }}/{pipeline_name}/{{{{ ds_nodash }}}}.csv"},
            {"type": "load_to_snowflake", "stage": "{{ auto }}", "table": get_input("Target Snowflake table")},
            {"type": "archive_s3", "source": f"s3://{{ auto }}/{pipeline_name}/{{{{ ds_nodash }}}}.csv", "archive": f"s3://{{ auto }}/archive/{pipeline_name}/"}
        ]

    else:
        print("❌ Unknown pipeline type.")
        return

    # Output DAG config YAML
    dag_path = Path("dag_configs") / f"{pipeline_name}.yaml"
    dag_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dag_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"✅ DAG config written to: {dag_path}")

    # Output GitHub mapping
    mapping = {
        "mappings": [
            {
                "file_name": f"{pipeline_name}.csv",
                "s3_location": f"s3://{{ auto }}/{pipeline_name}/{pipeline_name}.csv",
                "dag_config": f"s3://dag-configs/{pipeline_name}.yaml"
            }
        ]
    }
    map_path = Path("github_mappings") / f"{pipeline_name}.yaml"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, "w") as f:
        yaml.dump(mapping, f)
    print(f"✅ GitHub mapping written to: {map_path}")

if __name__ == "__main__":
    generate_config()
