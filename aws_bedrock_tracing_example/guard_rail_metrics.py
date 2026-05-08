import boto3
from datetime import datetime, timedelta

cloudwatch = boto3.client('cloudwatch')

# Fetch guardrail intervention metrics
response = cloudwatch.get_metric_statistics(
    Namespace='AWS/Bedrock/Guardrails',
    MetricName='InvocationsIntervened',
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=300,  # 5-minute intervals
    Statistics=['Sum', 'Average'],
    Dimensions=[
        {
            'Name': 'GuardrailId',
            'Value': 'your-guardrail-id'
        }
    ]
)

print("Intervention Count:", response['Datapoints'])

# Also track invocation latency
latency_response = cloudwatch.get_metric_statistics(
    Namespace='AWS/Bedrock/Guardrails',
    MetricName='InvocationLatency',
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=300,
    Statistics=['Average', 'Maximum'],
    Dimensions=[
        {
            'Name': 'GuardrailId',
            'Value': 'your-guardrail-id'
        }
    ]
)

print("Latency Metrics:", latency_response['Datapoints'])

# Track text unit consumption for cost tracking
text_unit_response = cloudwatch.get_metric_statistics(
    Namespace='AWS/Bedrock/Guardrails',
    MetricName='TextUnitCount',
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=300,
    Statistics=['Sum'],
    Dimensions=[
        {
            'Name': 'GuardrailId',
            'Value': 'your-guardrail-id'
        }
    ]
)

print("Text Units Evaluated:", text_unit_response['Datapoints'])
