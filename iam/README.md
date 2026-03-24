# IAM Policy — demo-lex-bedrock Lambda

The `policy.json` file contains the IAM permissions required by this Lambda function.

## Permissions

| Sid | Service | Actions | Purpose |
|-----|---------|---------|---------|
| CloudWatchLogsWrite | CloudWatch Logs | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | Standard Lambda logging |
| InvokeBedrockAgent | Bedrock | `bedrock:InvokeAgent` | Invoke Bedrock agents for conversation |
| InvokeAgentCoreRuntime | Bedrock AgentCore | `bedrock:InvokeAgentRuntime` | Invoke AgentCore runtime endpoint |
| UpdateConnectCustomerProfile | Customer Profiles | `profile:UpdateProfile` | Update Connect customer profiles with cotización |
| WriteOutboundCallTranscript | DynamoDB | `dynamodb:PutItem` | Persist USER/BOT transcript turns into `connect_outbound_call_transcript` |

## Placeholders

Replace the following placeholders with actual values before attaching:

- `<REGION>` — AWS region (e.g., `us-east-1`)
- `<ACCOUNT_ID>` — AWS account ID
- `<DOMAIN_NAME>` — Connect Customer Profiles domain name
