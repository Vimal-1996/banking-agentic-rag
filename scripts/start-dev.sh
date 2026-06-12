#!/bin/bash
echo "Starting Banking RAG dev environment..."
cd ~/banking-rag/terraform/environments/dev
terraform apply -auto-approve
echo ""
echo "All AWS resources running"
echo ""
terraform output
