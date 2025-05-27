```
2. Switching Traffic Between Deployments (Blue-Green Strategy)
Scenario: You want zero-downtime deployments in the same environment
This is where you have two versions running in the same environment and switch traffic between them.
Method 1: DNS-Based Traffic Switching with Route 53
Setup:
python# In your Pulumi infrastructure code
import pulumi_aws as aws

# Create a Route 53 hosted zone
hosted_zone = aws.route53.Zone(
    "chatbot-zone",
    name="chatbot.yourdomain.com",
)

# Create weighted routing records
blue_record = aws.route53.Record(
    "blue-record",
    zone_id=hosted_zone.zone_id,
    name="api.chatbot.yourdomain.com",
    type="CNAME",
    ttl=60,
    records=[blue_load_balancer.dns_name],
    set_identifier="blue",
    weighted_routing_policy=aws.route53.RecordWeightedRoutingPolicyArgs(
        weight=100,  # 100% traffic to blue initially
    ),
)

green_record = aws.route53.Record(
    "green-record",
    zone_id=hosted_zone.zone_id,
    name="api.chatbot.yourdomain.com",
    type="CNAME",
    ttl=60,
    records=[green_load_balancer.dns_name],
    set_identifier="green",
    weighted_routing_policy=aws.route53.RecordWeightedRoutingPolicyArgs(
        weight=0,  # 0% traffic to green initially
    ),
)
Switching Traffic:
bash# Switch from blue to green deployment
pulumi config set chatbot:blueWeight 0
pulumi config set chatbot:greenWeight 100
pulumi up
Method 2: Load Balancer Target Group Switching
Setup:
python# Create two target groups
blue_target_group = aws.lb.TargetGroup(
    "chatbot-blue-tg",
    port=80,
    protocol="HTTP",
    vpc_id=network["vpc"].id,
    health_check=aws.lb.TargetGroupHealthCheckArgs(
        path="/health",
        healthy_threshold=2,
        unhealthy_threshold=2,
    ),
)

green_target_group = aws.lb.TargetGroup(
    "chatbot-green-tg",
    port=80,
    protocol="HTTP",
    vpc_id=network["vpc"].id,
    health_check=aws.lb.TargetGroupHealthCheckArgs(
        path="/health",
        healthy_threshold=2,
        unhealthy_threshold=2,
    ),
)

# Load balancer listener with rules
listener = aws.lb.Listener(
    "chatbot-listener",
    load_balancer_arn=load_balancer.arn,
    port=80,
    default_actions=[
        aws.lb.ListenerDefaultActionArgs(
            type="forward",
            target_group_arn=blue_target_group.arn,  # Default to blue
        ),
    ],
)
Switching Traffic:
python# Configuration-based switching
config = pulumi.Config()
active_deployment = config.get("activeDeployment") or "blue"

# Choose target group based on configuration
active_target_group = blue_target_group if active_deployment == "blue" else green_target_group

# Update listener to use active target group
listener = aws.lb.Listener(
    "chatbot-listener",
    load_balancer_arn=load_balancer.arn,
    port=80,
    default_actions=[
        aws.lb.ListenerDefaultActionArgs(
            type="forward",
            target_group_arn=active_target_group.arn,
        ),
    ],
)
3. Practical GitHub Actions Workflow for Blue-Green Switching
Create .github/workflows/blue-green-deploy.yml:
yamlname: Blue-Green Deployment

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options: [staging, prod]
      deployment_strategy:
        description: 'Deployment strategy'
        required: true
        default: 'deploy-new'
        type: choice
        options:
          - deploy-new    # Deploy to inactive slot
          - switch-traffic # Switch traffic to other slot
          - rollback      # Rollback to previous slot

jobs:
  blue-green-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
  
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
  
      - name: Install dependencies
        run: |
          pip install pulumi pulumi-aws
  
      - name: Get current active deployment
        id: current-deployment
        run: |
          cd infrastructure
          pulumi stack select ${{ github.event.inputs.environment }}
          CURRENT=$(pulumi config get chatbot:activeDeployment || echo "blue")
          echo "current=$CURRENT" >> $GITHUB_OUTPUT
      
          # Determine next deployment slot
          if [ "$CURRENT" = "blue" ]; then
            echo "next=green" >> $GITHUB_OUTPUT
          else
            echo "next=blue" >> $GITHUB_OUTPUT
          fi
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
  
      - name: Deploy to inactive slot
        if: github.event.inputs.deployment_strategy == 'deploy-new'
        run: |
          cd infrastructure
          pulumi stack select ${{ github.event.inputs.environment }}
      
          # Deploy new version to inactive slot
          pulumi config set chatbot:deploymentTarget ${{ steps.current-deployment.outputs.next }}
          pulumi up --yes
      
          echo "Deployed new version to ${{ steps.current-deployment.outputs.next }} slot"
          echo "Current active slot: ${{ steps.current-deployment.outputs.current }}"
          echo "To switch traffic, run this workflow again with 'switch-traffic'"
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: ${{ secrets.AWS_REGION }}
  
      - name: Switch traffic
        if: github.event.inputs.deployment_strategy == 'switch-traffic'
        run: |
          cd infrastructure
          pulumi stack select ${{ github.event.inputs.environment }}
      
          # Switch active deployment
          pulumi config set chatbot:activeDeployment ${{ steps.current-deployment.outputs.next }}
          pulumi up --yes
      
          echo "Switched traffic from ${{ steps.current-deployment.outputs.current }} to ${{ steps.current-deployment.outputs.next }}"
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: ${{ secrets.AWS_REGION }}
  
      - name: Rollback
        if: github.event.inputs.deployment_strategy == 'rollback'
        run: |
          cd infrastructure
          pulumi stack select ${{ github.event.inputs.environment }}
      
          # Switch back to previous deployment
          pulumi config set chatbot:activeDeployment ${{ steps.current-deployment.outputs.current }}
          pulumi up --yes
      
          echo "Rolled back to ${{ steps.current-deployment.outputs.current }}"
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: ${{ secrets.AWS_REGION }}
```
