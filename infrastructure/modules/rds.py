import pulumi
import pulumi_aws as aws
import pulumi_random as random

def create_rds_instance(name, vpc_id, subnet_ids, security_group_ids):
    # Generate a random password for the database
    db_password = random.RandomPassword(
        f"{name}-password",
        length=16,
        special=False,
    )
    
    # Create a subnet group for the RDS instance
    subnet_group = aws.rds.SubnetGroup(
        f"{name}-subnet-group",
        subnet_ids=subnet_ids,
        tags={"Name": f"{name}-subnet-group"},
    )

    """
    When you create an RDS instance, AWS does not randomly pick subnets. Instead → AWS requires you to provide a Subnet Group, which defines allowed subnets.
    ✅ AWS will then launch the database in one (or more) of those subnets.
    ✅ For high availability (multi-AZ), AWS requires at least 2 subnets in different AZs → so that if one AZ goes down, DB still works.
    ✅ By using private subnets, you make sure:
        🚫 Database is not publicly accessible.
        ✅ Only your app servers inside VPC can reach the DB.
    """

    """
    DS Parameter Group is like a configuration profile for your database engine (PostgreSQL, MySQL, etc). 
    It defines the database engine settings → how the database behaves internally.
    When you launch an RDS instance, you can attach a Parameter Group.
        If you don't → AWS uses the default one → which might not have the settings you want.
        If you want to customize DB behavior → you need to create and attach your own Parameter Group.

    "family="postgres13" → defines the database engine version family.
        postgres13 → means → this parameter group is for PostgreSQL version 13.x
        You must match this with the version of the RDS instance you will create later.

    log_connections = 1 → log every time a client connects to the database.
    """

    # Create a parameter group for PostgreSQL
    db_parameter_group = aws.rds.ParameterGroup("db-param-group",
        family="postgres17",  # Choose the appropriate version
        description="Parameter group for chatbot PostgreSQL",
        parameters=[
            aws.rds.ParameterGroupParameterArgs(
                name="log_connections",
                value="1"
            ),
            aws.rds.ParameterGroupParameterArgs(
                name="log_disconnections",
                value="1"
            )
        ],
        tags={
            "Name": "chatbot-db-param-group",
            "Project": "fastapi-chatbot"
        }
    )
    
    # Create the RDS instance
    db_instance = aws.rds.Instance(
        f"{name}-db",
        allocated_storage=20,
        storage_type="gp2",
        engine="postgres",
        engine_version="17.4",
        instance_class="db.t3.micro",
        db_name="chatbot",
        username="dbadmin",
        password=db_password.result,
        parameter_group_name=db_parameter_group.name, # "default.postgres17",
        skip_final_snapshot=True,  # For development only
        vpc_security_group_ids=security_group_ids,
        db_subnet_group_name=subnet_group.name,
        publicly_accessible=False,  # Even though in public subnet, restrict direct public access
        multi_az=False,  # For production, set to true for high availability
        backup_retention_period=0,  # Disable automated backups for free tier
        apply_immediately=True,
        tags={"Name": f"{name}-db"},
    )
    
    return {
        "instance": db_instance,
        "password": db_password.result,
        "username": "dbadmin",
        "database": "chatbot",
    }