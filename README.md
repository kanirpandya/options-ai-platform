# options-ai-platform

AI-powered options strategy platform.

Components:
- engine: strategy computation & agentic analysis
- backend: AWS async job processing
- infra: CDK stacks (backend + frontend)
- frontend: UI (future)

Architecture (v1): API Gateway -> Lambda -> SQS -> Fargate -> DynamoDB + S3
