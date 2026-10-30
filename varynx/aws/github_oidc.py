"""GitHub Actions OIDC + AWS IAM CI/CD configuration."""
WORKFLOW_TEMPLATE = """
# .github/workflows/deploy.yml
# GitHub Actions deploy workflow using OIDC for keyless AWS auth.
name: Deploy Varynx
on:
  push:
    branches: [main, master]
permissions:
  id-token: write
  contents: read
env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: varynx-api
  ECS_SERVICE: varynx-api
  ECS_CLUSTER: varynx-cluster
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2
      - name: Build and push
        run: |
          docker build -t ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }} .
          docker push ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
      - name: Deploy to ECS
        run: aws ecs update-service --cluster ${{ env.ECS_CLUSTER }} --service ${{ env.ECS_SERVICE }} --force-new-deployment
"""
def get_workflow_yaml() -> str: return WORKFLOW_TEMPLATE