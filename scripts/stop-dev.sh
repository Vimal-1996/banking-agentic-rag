#!/bin/bash
echo "Stopping Banking RAG dev environment..."
cd ~/banking-rag/terraform/environments/dev
terraform output > ~/banking-rag/docs/terraform-outputs.txt
echo "Outputs saved"
terraform destroy -auto-approve
echo ""
echo "All AWS resources destroyed"
echo "Cost is now ~\$0"
