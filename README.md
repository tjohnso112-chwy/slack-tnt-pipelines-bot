# Slack Bot: Tier 1 Upload Mode

This version of the Slack bot is optimized for non-technical users (Tier 1). It supports:

✅ Uploading files to **existing pipelines**  
✅ Creating **new pipelines** by providing just a name and a sample file

---

## 🧑‍💼 How It Works

1. Run the Slack command:
   ```
   /upload-pipeline
   ```

2. The bot asks:
   > Are you creating a new pipeline or uploading to an existing one?

3. If "existing", bot shows numbered list of known pipelines (from `dag_configs/*.yaml`)
   > User replies with number and uploads CSV

4. If "new", bot asks for:
   - Name of new pipeline
   - A CSV file to start the setup

---

## 🪣 Behind the Scenes

- Files are uploaded to:
  ```
  s3://chewy-ingest/<pipeline_name>/<filename>.csv
  ```

- No technical inputs are required (no stages, buckets, or SQL)
- New pipeline requests are logged and reviewed manually

---

## 🧪 Testing

1. Deploy using Terraform and Lambda (see original README for instructions)
2. Test `/upload-pipeline` in Slack with:
   - `new` → pipeline name + file
   - `existing` → number + file

---

## 🛡️ Permissions & Access

- Slack app requires: `commands`, `chat:write`, `files:read`
- AWS Lambda must have S3 upload permissions


---

## 🔁 Auto-Triggering Airflow DAGs After Upload

After a file is uploaded, the bot now automatically triggers the corresponding Airflow DAG using MWAA's REST API.

### 🔧 Configuration

1. **Enable MWAA REST API** in your AWS environment.
2. **Set Lambda Environment Variables** (via Terraform):

```
MWAA_API_URL     = "https://<your-env>.airflow.amazonaws.com/api/v1"
MWAA_USER        = "airflow"            # Optional if using IAM auth
MWAA_PASSWORD    = "your-password"
```

3. **Your DAGs must accept `conf`**, like this:

```python
@task
def ingest_file(**kwargs):
    path = kwargs["dag_run"].conf.get("uploaded_file")
    print(f"Processing: {path}")
```

4. The Slack bot triggers the DAG using:

```python
trigger_dag(dag_id=pipeline, conf={"uploaded_file": key})
```

This makes ingestion automatic — no manual steps needed after file upload.
