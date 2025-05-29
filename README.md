# Slack Bot: Tier 1 Upload Mode

This Slack bot enables non-technical users to upload CSV files to data pipelines via Slack, with minimal input. It abstracts away AWS, S3, and Airflow details, providing a simple `/upload-pipeline` command in Slack.

---

## 🧑‍💼 User Workflow

1. **Run the Slack command:**
   ```
   /upload-pipeline
   ```

2. **Bot prompts:**
   > Are you creating a new pipeline or uploading to an existing one?

3. **If "existing":**
   - Bot fetches pipeline names from `dag_configs/*.yaml`
   - Presents a numbered list to the user
   - User replies with a number and uploads a CSV file

4. **If "new":**
   - Bot asks for a pipeline name
   - User provides a name and uploads a CSV file
   - Bot logs the request for manual review

---

## 🏗️ Technical Architecture

### 1. **Slack App**

- **Slash Command:** `/upload-pipeline`
- **Scopes Required:** `commands`, `chat:write`, `files:read`
- **Interactivity:** Uses Slack's interactive messages and file uploads

### 2. **AWS Lambda Handler**

- **Entry Point:** Receives Slack events via API Gateway
- **Slack Verification:** Validates Slack signing secret
- **Session State:** Maintains user session state (e.g., pipeline selection) in DynamoDB or in-memory (stateless fallback)
- **File Handling:**
  - Downloads uploaded file from Slack using `files:read` scope and Slack Web API
  - Validates file type (CSV only)
  - Renames file for S3 key: `s3://chewy-ingest/<pipeline_name>/<filename>.csv`
  - Uploads file to S3 using `boto3`

### 3. **Pipeline Discovery**

- **Source:** Reads YAML files from `dag_configs/*.yaml` (bundled with Lambda or fetched from S3/Git)
- **Parsing:** Extracts pipeline names and metadata for user selection

### 4. **New Pipeline Requests**

- **Logging:** New pipeline requests (name + sample file) are logged to a DynamoDB table or S3 bucket for manual review
- **No automatic DAG creation** — requests are reviewed and provisioned by engineers

### 5. **Airflow DAG Triggering**

- **After S3 Upload:** Lambda triggers the corresponding Airflow DAG via MWAA REST API
- **API Call:** Uses `POST /dags/{dag_id}/dagRuns` with a JSON payload:
  ```json
  {
    "conf": {
      "uploaded_file": "<s3_key>"
    }
  }
  ```
- **Authentication:** Uses MWAA basic auth or IAM (credentials set via Lambda environment variables)
- **DAG Requirements:** DAG must accept `conf` and handle the `uploaded_file` parameter

---

## 🪣 S3 File Storage

- **Bucket:** `chewy-ingest`
- **Key Format:** `<pipeline_name>/<filename>.csv`
- **Permissions:** Lambda must have `s3:PutObject` on the bucket

---

## 🔁 Airflow Integration

- **MWAA REST API:** Must be enabled in your AWS environment
- **Lambda Environment Variables:**
  ```
  MWAA_API_URL     = "https://<your-env>.airflow.amazonaws.com/api/v1"
  MWAA_USER        = "airflow"            # Optional if using IAM auth
  MWAA_PASSWORD    = "your-password"
  ```
- **DAG Example:**
  ```python
  @task
  def ingest_file(**kwargs):
      path = kwargs["dag_run"].conf.get("uploaded_file")
      print(f"Processing: {path}")
  ```
- **Trigger Example:**
  ```python
  trigger_dag(dag_id=pipeline, conf={"uploaded_file": key})
  ```

---

## 🔒 Security & Permissions

- **Slack App:** Only accessible to authorized Slack workspace users
- **AWS Lambda:** IAM role must allow:
  - `s3:PutObject` (for file upload)
  - `secretsmanager:GetSecretValue` (if using Secrets Manager for MWAA credentials)
  - `dynamodb:PutItem` (if logging new pipeline requests)
  - Outbound HTTPS to MWAA API
- **Slack Verification:** All requests are verified using Slack's signing secret

---

## 🧪 Testing & Deployment

1. **Deploy Infrastructure:**
   - Use Terraform to provision Lambda, API Gateway, IAM roles, S3 bucket, and (optionally) DynamoDB
   - Deploy Lambda code (zip or container)

2. **Configure Slack App:**
   - Set up `/upload-pipeline` slash command pointing to API Gateway endpoint
   - Add required OAuth scopes

3. **Test End-to-End:**
   - `/upload-pipeline` in Slack
   - Try both "new" and "existing" flows
   - Confirm file appears in S3 and DAG is triggered

---

## 📝 File & Code Structure

- `lambda_function.py` — Main Lambda handler for Slack events
- `slack_client.py` — Slack API utilities (file download, message send)
- `airflow_client.py` — MWAA REST API integration
- `dag_configs/` — YAML files listing available pipelines
- `terraform/` — Infrastructure as code

---

## 🛠️ Extending & Customizing

- **Add pipeline metadata:** Extend `dag_configs/*.yaml` with owners, descriptions, etc.
- **Custom validation:** Add CSV schema checks in Lambda
- **Notifications:** Integrate with email or Slack for new pipeline requests
- **Audit logging:** Log all uploads and triggers to CloudWatch or DynamoDB

---

## 🚧 Limitations

- Only supports CSV uploads
- New pipelines require manual provisioning
- No support for multi-file or zipped uploads
- Assumes Airflow DAGs are pre-configured to accept `uploaded_file` via `conf`

---

## 📚 References

- [Slack API: Interactivity & Slash Commands](https://api.slack.com/interactivity/slash-commands)
- [AWS Lambda Python](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [MWAA REST API](https://docs.aws.amazon.com/mwaa/latest/userguide/airflow-rest-api.html)
- [boto3 S3 Docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)

---

## 🏗️ Infrastructure as Code: Terraform Breakdown

This project uses [Terraform](https://www.terraform.io/) to provision and manage all AWS resources required for the Slack pipeline upload bot. Below is a detailed explanation of each resource, its purpose, and how it fits into the overall architecture.

### 1. **AWS Provider**

```hcl
provider "aws" {
  region = "us-east-1"
}
```
- **Purpose:** Configures Terraform to use AWS as the cloud provider in the `us-east-1` region.
- **Why:** All resources (Lambda, API Gateway, IAM, etc.) will be created in this region.

---

### 2. **API Gateway**

#### a. **REST API**

```hcl
resource "aws_api_gateway_rest_api" "slack_bot" {
  name = "SlackBotAPI"
}
```
- **Purpose:** Creates a new REST API in API Gateway.
- **Why:** Serves as the HTTPS endpoint for Slack to send slash command events to your backend.

#### b. **Resource Path**

```hcl
resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.slack_bot.id
  parent_id   = aws_api_gateway_rest_api.slack_bot.root_resource_id
  path_part   = "upload-pipeline"
}
```
- **Purpose:** Adds the `/upload-pipeline` path to the API.
- **Why:** This matches the Slack slash command endpoint.

#### c. **HTTP Method**

```hcl
resource "aws_api_gateway_method" "upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.slack_bot.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "POST"
  authorization = "NONE"
}
```
- **Purpose:** Allows POST requests on `/upload-pipeline`.
- **Why:** Slack sends POST requests for slash commands and file uploads.

#### d. **Integration with Lambda**

```hcl
resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.slack_bot.id
  resource_id             = aws_api_gateway_resource.upload.id
  http_method             = aws_api_gateway_method.upload_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.slack_handler.invoke_arn
}
```
- **Purpose:** Connects API Gateway to the Lambda function using AWS_PROXY integration.
- **Why:** Forwards the entire HTTP request to Lambda, enabling flexible event handling.

---

### 3. **AWS Lambda**

```hcl
resource "aws_lambda_function" "slack_handler" {
  filename         = "deployment_package.zip"
  function_name    = "slack_pipeline_bot"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "wsgi_handler.handler"
  runtime          = "python3.10"
  source_code_hash = filebase64sha256("deployment_package.zip")
  environment {
    variables = {
      SLACK_BOT_TOKEN = var.slack_token
      S3_BUCKET       = "chewy-ingest"
    }
  }
}
```
- **Purpose:** Deploys the main Python Lambda function that processes Slack events.
- **Why:** This is the core backend logic for the bot, handling Slack requests, file downloads, S3 uploads, and Airflow triggers.
- **Key Details:**
  - **Handler:** Entry point for Lambda (e.g., Flask or AWS Lambda handler).
  - **Environment Variables:** Passes secrets and configuration (Slack token, S3 bucket name).

---

### 4. **IAM Roles and Permissions**

#### a. **Lambda Execution Role**

```hcl
resource "aws_iam_role" "lambda_exec" {
  name = "lambda_exec_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Effect = "Allow"
        Sid    = ""
      },
    ]
  })
}
```
- **Purpose:** Grants Lambda permission to assume this role.
- **Why:** Required for Lambda to run and access AWS resources.

#### b. **Attach Basic Execution Policy**

```hcl
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
```
- **Purpose:** Allows Lambda to write logs to CloudWatch.
- **Why:** Essential for debugging and monitoring.

---

### 5. **Lambda Permission for API Gateway**

```hcl
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.slack_bot.execution_arn}/*/*"
}
```
- **Purpose:** Grants API Gateway permission to invoke the Lambda function.
- **Why:** Required for the integration to work securely.

---

### 6. **How It All Fits Together**

- **Slack** sends a POST request to the API Gateway endpoint when a user runs `/upload-pipeline`.
- **API Gateway** receives the request at `/upload-pipeline` and forwards it to the Lambda function.
- **Lambda** processes the event, interacts with Slack APIs, downloads files, uploads to S3, and triggers Airflow.
- **IAM Roles** ensure Lambda has the necessary permissions to execute, log, and interact with other AWS services.

---

### 7. **Extending the Terraform**

- **Add S3 Bucket Resource:** If not already present, define the S3 bucket for uploads.
- **Add DynamoDB Table:** For session state or logging new pipeline requests.
- **Add Secrets Manager:** To securely store Slack tokens or Airflow credentials.
- **Add More IAM Policies:** For S3, DynamoDB, MWAA API, etc.

---

**Summary:**  
Terraform automates the creation and configuration of all AWS infrastructure needed for the Slack pipeline upload bot, ensuring repeatable, secure, and auditable deployments.
