# AWS Migration Path — Concur History Explorer

## Phase 1 — Prototype (Current State)

| Component | Technology |
|-----------|-----------|
| Database | SQLite (`db/concur.db`) |
| Compute | Streamlit local server (`streamlit run`) |
| Image storage | Local filesystem (`db/images/`) |
| Auth | Shared password via `st.secrets` |
| Infra | Single machine / Docker container |

**Limitations:** Single-writer SQLite, local images, no MFA, no audit log.

---

## Phase 2 — AWS Deployment

### Database
- Migrate from SQLite → **Amazon RDS PostgreSQL** (`db.t3.micro`, ~$15/month)
  or **Aurora Serverless v2** (scales to zero when idle, ~$0–$30/month depending on usage)
- Schema migration via **Alembic** (`alembic upgrade head`)
- Bulk import: export SQLite to CSV → `COPY` into RDS via psql
- Connection string injected via ECS task environment / AWS Secrets Manager
- SQLite WAL pragmas → remove; PostgreSQL handles concurrency natively

### Image Storage
- Move receipt images from local filesystem → **Amazon S3**
- Bucket: `icw-concur-receipts` (private, no public access)
- Access via **pre-signed URLs** (TTL: 15 minutes, generated per request)
- Lifecycle policy: expire objects after 7 years (per ICW Group retention policy)
- Code change: update `app/utils/image_handler.py` to call `s3.generate_presigned_url()`

### Compute
- Package app as Docker image → push to **Amazon ECR**
- Deploy on **AWS App Runner** or **ECS Fargate** (0.25 vCPU / 0.5 GB RAM, ~$10/month)
- Health check: `/_stcore/health` (already in Dockerfile)
- Auto-scaling: 1 task minimum, 3 maximum (matches 3 authorized users)

### Authentication
- Replace `st.secrets` password → **Amazon Cognito User Pool**
- 3 named users from Finance Travel/Expense team
- MFA enabled (TOTP or SMS)
- App client → Authorization Code Grant → Streamlit session cookie
- Implementation: `streamlit-cognito-auth` library or custom OAuth2 callback

### Networking
- **Application Load Balancer** with HTTPS (ACM certificate)
- Security group: inbound 443 restricted to ICW corporate IP range(s)
- RDS in **private subnets** (no internet access)
- Fargate tasks in private subnets, outbound via NAT Gateway

### Monitoring
- **CloudWatch Logs** — forward `logs/app.log` via CloudWatch agent or awslogs driver
- Basic alarms: error rate > 5 in 5 minutes, task health check failures
- Optional: CloudWatch dashboard for usage metrics (searches/exports per day)

### Estimated Monthly Cost (Phase 2)

| Service | Estimate |
|---------|---------|
| RDS PostgreSQL db.t3.micro | ~$15 |
| ECS Fargate (1 task) | ~$10 |
| S3 storage (< 50 GB receipts) | ~$2 |
| ALB | ~$8 |
| Data transfer, misc | ~$5 |
| **Total** | **~$40/month** |

---

## Phase 3 — Future Enhancements

- **FastAPI layer** — expose REST endpoints if other internal systems (Workday, BI tools)
  need programmatic access to the historical data
- **Automated retention enforcement** — Lambda function triggered monthly:
  delete ct_report_entry rows with `TRANSACTION_DATE < NOW() - 7 years`,
  remove corresponding S3 objects, run VACUUM/ANALYZE
- **Workday cross-reference** — join on employee ID or cost center to enrich
  historical Concur data with current Workday org structure
- **Audit log** — write every search/export to a separate `audit_log` table
  (timestamp, user, action, parameters) for compliance reporting

---

## PII Data Notice

`ct_employee` contains: `FIRST_NAME`, `LAST_NAME`, `EMAIL_ADDRESS`, `EMPLOYEE_ID`.  
`ct_report_entry` contains: expense amounts, vendor names, location data.

**Production requirements:**
- Encryption at rest: RDS storage encryption enabled (AES-256)
- Encryption in transit: TLS 1.2+ enforced on ALB and RDS
- Access logs retained per ICW data governance policy
- IAM roles follow least-privilege (app role: read-only S3 + RDS)
