# HalaTuju API - Cloud Run Deployment

## Prerequisites

1. Google Cloud SDK installed (`gcloud`)
2. Docker installed (for local testing)
3. GCP project with Cloud Run API enabled

## Environment Variables

Set these in Cloud Run:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `your-random-secret-key` |
| `DATABASE_URL` | Supabase Session Pooler URI | `postgresql://postgres.xxx:password@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres` |
| `ALLOWED_HOSTS` | Comma-separated hosts | `api.halatuju.my,halatuju-api-xxx.run.app` |
| `CORS_ALLOWED_ORIGINS` | Frontend URLs | `https://halatuju.my,http://localhost:3000` |
| `CSRF_TRUSTED_ORIGINS` | Same as CORS | `https://halatuju.my` |
| `SUPABASE_URL` | For auth verification | `https://pbrrlyoyyiftckqvzvvo.supabase.co` |
| `SUPABASE_JWT_SECRET` | JWT verification secret | Get from Supabase dashboard |
| `GEMINI_API_KEY` | For AI reports | Your Gemini API key |
| `SENTRY_DSN` | Error tracking (optional) | `https://xxx@sentry.io/xxx` |

## Deploy Commands

### Option A: Direct Deploy (Recommended)

```bash
cd halatuju_api

# Set project
gcloud config set project halatuju

# Deploy to Cloud Run (asia-southeast1 = Singapore)
gcloud run deploy halatuju-api \
  --source . \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars "DJANGO_SETTINGS_MODULE=halatuju.settings.production" \
  --set-env-vars "SECRET_KEY=your-secret-key" \
  --set-env-vars "DATABASE_URL=postgresql://postgres.xxx:password@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres" \
  --set-env-vars "ALLOWED_HOSTS=halatuju-api-xxx.run.app" \
  --set-env-vars "CORS_ALLOWED_ORIGINS=https://halatuju.my" \
  --set-env-vars "CSRF_TRUSTED_ORIGINS=https://halatuju.my" \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3
```

### Option B: Build & Deploy Separately

```bash
# Build image
gcloud builds submit --tag gcr.io/halatuju/halatuju-api

# Deploy from image
gcloud run deploy halatuju-api \
  --image gcr.io/halatuju/halatuju-api \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated
```

## Custom Domain

After deployment:

1. Go to Cloud Run console
2. Click on halatuju-api service
3. "Manage Custom Domains" > "Add Mapping"
4. Map `api.halatuju.my` to the service
5. Update DNS CNAME record

## Testing

```bash
# Health check
curl https://api.halatuju.my/api/v1/courses/

# Eligibility check
curl -X POST https://api.halatuju.my/api/v1/eligibility/check/ \
  -H "Content-Type: application/json" \
  -d '{"grades": {"BM": "A", "BI": "B", "MAT": "B", "SEJ": "C", "PI": "A"}, "gender": "female", "nationality": "malaysian"}'
```

## Rollback

```bash
# List revisions
gcloud run revisions list --service halatuju-api --region asia-southeast1

# Rollback to previous revision
gcloud run services update-traffic halatuju-api \
  --region asia-southeast1 \
  --to-revisions=halatuju-api-00001-abc=100
```
