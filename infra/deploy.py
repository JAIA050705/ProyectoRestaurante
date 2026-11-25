#!/usr/bin/env python3
"""
deploy.py - builds the Restaurant Review Platform on AWS, from code (no console clicks).

Commands (run them in this order the first time):
    python deploy.py base   --war C:\\path\\RestaurantReviewAPI.war
        Creates what the server needs: SSH key, firewall, S3 bucket, secrets in
        Parameter Store. Uploads the WAR and the database schema. No server yet.
    python deploy.py server
        Launches the EC2 server with a fixed IP, installs everything by itself
        (Java, MySQL, GlassFish, nginx), creates health alarms and waits until
        the API answers.
    python deploy.py status
        Shows what exists and whether the API is answering.
    python deploy.py update --war PATH
        Uploads a new WAR. The server deploys it by itself within a minute.
    python deploy.py rollback
        Goes back to the WAR that was running before the last update.
    python deploy.py stop / start
        Stops the server when nobody uses it (data and IP stay) and starts it again.
    python deploy.py deployer
        Installs the latest WAR deployer script on the running server.

Everything is idempotent: running a command twice does not duplicate anything.
Every resource is tagged Project=restaurant-review. destroy.py removes them.
"""
import argparse
import datetime
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request

from botocore.exceptions import ClientError

import config

HERE = os.path.dirname(os.path.abspath(__file__))


def say(message):
    print(message, flush=True)


def client_code(error):
    return error.response["Error"]["Code"]


# ---------------------------------------------------------------- base pieces

def default_network(ec2):
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        raise SystemExit("There is no default VPC in this region. Run preflight.py and tell me.")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    subnets.sort(key=lambda s: s["AvailabilityZone"])
    return vpc_id, subnets[0]["SubnetId"], subnets[0]["AvailabilityZone"]


def my_public_ip():
    try:
        with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=10) as response:
            return response.read().decode().strip()
    except Exception:
        return None


def ensure_key(ec2, key_name, pem_path):
    try:
        ec2.describe_key_pairs(KeyNames=[key_name])
        if not os.path.exists(pem_path):
            raise SystemExit(
                f"The key pair '{key_name}' exists in AWS but {pem_path} is not on this computer.\n"
                f"Without the .pem you cannot use SSH. Run: python destroy.py --delete-key  and then base again,\n"
                f"or use another name with --key-name.")
        say(f"  key pair {key_name}: already exists")
        return
    except ClientError as error:
        if client_code(error) != "InvalidKeyPair.NotFound":
            raise
    created = ec2.create_key_pair(KeyName=key_name, KeyType="rsa", TagSpecifications=[config.tag_spec("key-pair", key_name)])
    with open(pem_path, "w", newline="\n") as handle:
        handle.write(created["KeyMaterial"])
    try:
        os.chmod(pem_path, 0o600)
    except OSError:
        pass
    say(f"  key pair {key_name}: created, private key saved in {pem_path}")


def ensure_security_group(ec2, vpc_id, ssh_cidr):
    found = ec2.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [config.SG_NAME]}, {"Name": "vpc-id", "Values": [vpc_id]}])["SecurityGroups"]
    if found:
        group = found[0]
        group_id = group["GroupId"]
        say(f"  security group {config.SG_NAME}: already exists ({group_id})")
    else:
        group_id = ec2.create_security_group(
            GroupName=config.SG_NAME, Description="Restaurant Review web server (HTTP and SSH from one address)",
            VpcId=vpc_id, TagSpecifications=[config.tag_spec("security-group", config.SG_NAME)])["GroupId"]
        group = ec2.describe_security_groups(GroupIds=[group_id])["SecurityGroups"][0]
        say(f"  security group {config.SG_NAME}: created ({group_id})")

    def allow(port, cidr, description):
        try:
            ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[{
                "IpProtocol": "tcp", "FromPort": port, "ToPort": port,
                "IpRanges": [{"CidrIp": cidr, "Description": description}]}])
        except ClientError as error:
            if client_code(error) != "InvalidPermission.Duplicate":
                raise

    allow(80, "0.0.0.0/0", "HTTP for everybody")
    # SSH only from one address; if your address changed, the old rule is replaced
    wanted = [ssh_cidr] if ssh_cidr else []
    for permission in group.get("IpPermissions", []):
        if permission.get("FromPort") == 22:
            for rng in permission.get("IpRanges", []):
                if rng["CidrIp"] not in wanted:
                    ec2.revoke_security_group_ingress(GroupId=group_id, IpPermissions=[{
                        "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": rng["CidrIp"]}]}])
    if ssh_cidr:
        allow(22, ssh_cidr, "SSH from the admin address")
        say(f"  firewall: port 80 open to everybody, port 22 only from {ssh_cidr}")
    else:
        say("  firewall: port 80 open to everybody, SSH closed (no --ssh-cidr and could not detect your IP)")
    return group_id


def ensure_bucket(s3, name, region):
    try:
        args = {"Bucket": name}
        if region != "us-east-1":
            args["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**args)
        say(f"  S3 bucket {name}: created")
    except ClientError as error:
        if client_code(error) not in ("BucketAlreadyOwnedByYou",):
            raise
        say(f"  S3 bucket {name}: already exists")
    s3.put_public_access_block(Bucket=name, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_tagging(Bucket=name, Tagging={"TagSet": config.tag_list(name)})
    s3.put_bucket_lifecycle_configuration(Bucket=name, LifecycleConfiguration={"Rules": [{
        "ID": "expire-old-backups", "Status": "Enabled", "Filter": {"Prefix": "backups/"},
        "Expiration": {"Days": 30}}]})
    say("  S3 bucket: public access blocked, backups expire after 30 days")


def ensure_secrets(ssm):
    created = []
    for name in ("db_password", "db_root_password", "jwt_secret"):
        full = f"{config.PARAM_PREFIX}/{name}"
        try:
            ssm.put_parameter(Name=full, Value=secrets.token_urlsafe(32), Type="SecureString",
                              Description="Generated by deploy.py", Tags=config.tag_list(name))
            created.append(name)
        except ClientError as error:
            if client_code(error) != "ParameterAlreadyExists":
                raise
    if created:
        say(f"  secrets generated and stored encrypted in Parameter Store: {', '.join(created)}")
    else:
        say("  secrets: already exist (never overwritten)")


def put_string_param(ssm, name, value):
    full = f"{config.PARAM_PREFIX}/{name}"
    try:
        ssm.put_parameter(Name=full, Value=value, Type="String", Overwrite=True)
        ssm.add_tags_to_resource(ResourceType="Parameter", ResourceId=full, Tags=config.tag_list(name))
    except ClientError as error:
        if client_code(error) != "ParameterAlreadyExists":
            raise


def get_param(ssm, name, default=None):
    try:
        return ssm.get_parameter(Name=f"{config.PARAM_PREFIX}/{name}")["Parameter"]["Value"]
    except ClientError as error:
        if client_code(error) == "ParameterNotFound":
            return default
        raise


def upload_war(s3, ssm, bucket, war_path):
    if not os.path.isfile(war_path):
        raise SystemExit(f"The WAR file was not found: {war_path}")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"wars/{config.CONTEXT_ROOT}-{stamp}.war"
    s3.upload_file(war_path, bucket, key)
    previous = get_param(ssm, "war_key")
    if previous:
        put_string_param(ssm, "war_key_previous", previous)
    put_string_param(ssm, "war_key", key)
    say(f"  WAR uploaded as s3://{bucket}/{key} ({os.path.getsize(war_path) // 1024} KB)")
    prune_old_wars(s3, bucket, keep=config.KEEP_WARS, protect={key, previous})
    return key


def prune_old_wars(s3, bucket, keep, protect):
    objects = s3.list_objects_v2(Bucket=bucket, Prefix="wars/").get("Contents", [])
    objects.sort(key=lambda o: o["Key"], reverse=True)
    for old in objects[keep:]:
        if old["Key"] not in protect:
            s3.delete_object(Bucket=bucket, Key=old["Key"])


def upload_schema(s3, bucket, schema_path):
    if not os.path.isfile(schema_path):
        raise SystemExit(f"The schema file was not found: {schema_path}\nUse --schema PATH.")
    s3.upload_file(schema_path, bucket, "db/schema.sql")
    say("  database schema uploaded to S3")


# -------------------------------------------------------------------- commands

def cmd_base(args, session):
    ec2, s3, ssm = (session.client(n) for n in ("ec2", "s3", "ssm"))
    bucket = config.bucket_name(session, args.region)
    say(f"Creating the base in {args.region}")
    vpc_id, _, _ = default_network(ec2)
    ssh_cidr = args.ssh_cidr
    if not ssh_cidr:
        ip = my_public_ip()
        ssh_cidr = f"{ip}/32" if ip else None
    ensure_key(ec2, args.key_name, os.path.join(HERE, f"{args.key_name}.pem"))
    ensure_security_group(ec2, vpc_id, ssh_cidr)
    ensure_bucket(s3, bucket, args.region)
    ensure_secrets(ssm)
    upload_schema(s3, bucket, args.schema)
    if args.war:
        upload_war(s3, ssm, bucket, args.war)
    elif not get_param(ssm, "war_key"):
        say("  (no WAR yet: run base again with --war before 'server')")
    say("\nBase ready. Next: python deploy.py server")


def render_user_data(bucket, region):
    with open(os.path.join(HERE, "bootstrap", "user_data.sh"), encoding="utf-8") as handle:
        text = handle.read()
    values = {"BUCKET": bucket, "REGION": region, "PARAM_PREFIX": config.PARAM_PREFIX,
              "GF_VERSION": config.GLASSFISH_VERSION, "CONNECTOR_VERSION": config.MYSQL_CONNECTOR_VERSION,
              "CONTEXT": config.CONTEXT_ROOT}
    for name, value in values.items():
        text = text.replace(f"@@{name}@@", value)
    if "@@" in text:
        raise SystemExit("A marker was left unreplaced in bootstrap/user_data.sh")
    if len(text.encode()) > 16000:
        raise SystemExit("user_data.sh is bigger than the 16 KB limit of EC2")
    return text.replace("\r\n", "\n")


def ensure_elastic_ip(ec2, instance_id):
    found = config.find_addresses(ec2)
    if found:
        allocation = found[0]["AllocationId"]
        ip = found[0]["PublicIp"]
        say(f"  Elastic IP {ip}: already exists")
    else:
        created = ec2.allocate_address(Domain="vpc", TagSpecifications=[config.tag_spec("elastic-ip", config.EIP_NAME)])
        allocation, ip = created["AllocationId"], created["PublicIp"]
        say(f"  Elastic IP {ip}: allocated")
    ec2.associate_address(InstanceId=instance_id, AllocationId=allocation, AllowReassociation=True)
    return ip


def ensure_alarms(session, instance_id, region):
    cw = session.client("cloudwatch")

    def alarm(name, metric, action):
        cw.put_metric_alarm(
            AlarmName=name, Namespace="AWS/EC2", MetricName=metric,
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}], Statistic="Maximum",
            Period=60, EvaluationPeriods=3, Threshold=1, ComparisonOperator="GreaterThanOrEqualToThreshold",
            AlarmActions=[f"arn:aws:automate:{region}:ec2:{action}"], Tags=config.tag_list(name))

    alarm("rr-instance-check-failed", "StatusCheckFailed_Instance", "reboot")
    try:
        alarm("rr-system-check-failed", "StatusCheckFailed_System", "recover")
        say("  alarms: reboot if the instance check fails, recover if the host fails")
    except ClientError as error:
        alarm("rr-system-check-failed", "StatusCheckFailed_System", "reboot")
        say(f"  alarms: 'recover' not allowed here ({client_code(error)}); using reboot for both")


def health(ip):
    """Returns the HTTP status of the API list endpoint, or None if nothing answers."""
    url = f"http://{ip}/{config.CONTEXT_ROOT}/api/restaurants"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except Exception:
        return None


def show_console_tail(ec2, instance_id):
    try:
        output = ec2.get_console_output(InstanceId=instance_id, Latest=True).get("Output", "")
    except ClientError:
        return
    lines = output.strip().splitlines()[-40:]
    say("\nLast lines of the instance console:\n" + "\n".join(lines))


def cmd_server(args, session):
    ec2, ssm, s3 = (session.client(n) for n in ("ec2", "ssm", "s3"))
    bucket = config.bucket_name(session, args.region)
    if not get_param(ssm, "war_key"):
        raise SystemExit("No WAR in S3 yet. Run: python deploy.py base --war PATH_TO_WAR")
    vpc_id, subnet_id, zone = default_network(ec2)
    groups = ec2.describe_security_groups(Filters=[
        {"Name": "group-name", "Values": [config.SG_NAME]}, {"Name": "vpc-id", "Values": [vpc_id]}])["SecurityGroups"]
    if not groups:
        raise SystemExit("The base is not ready. Run: python deploy.py base --war PATH_TO_WAR")

    existing = config.find_instances(ec2)
    if existing and args.recreate:
        old_ids = [i["InstanceId"] for i in existing]
        say(f"--recreate: terminating {', '.join(old_ids)} (the Elastic IP, firewall and S3 data are kept)")
        ec2.terminate_instances(InstanceIds=old_ids)
        ec2.get_waiter("instance_terminated").wait(InstanceIds=old_ids)
        existing = []
    if existing:
        instance = existing[0]
        instance_id = instance["InstanceId"]
        say(f"The server already exists ({instance_id}, {instance['State']['Name']}).")
        if instance["State"]["Name"] == "stopped":
            ec2.start_instances(InstanceIds=[instance_id])
            say("  starting it again")
    else:
        arch = args.arch
        ami = session.client("ssm").get_parameter(
            Name=f"/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-{arch}")["Parameter"]["Value"]
        instance_type = args.instance_type or ("t4g.small" if arch == "arm64" else "t3.small")
        say(f"Launching {instance_type} ({arch}) with Amazon Linux 2023 in {zone}")
        launched = ec2.run_instances(
            ImageId=ami, InstanceType=instance_type, MinCount=1, MaxCount=1,
            KeyName=args.key_name, SecurityGroupIds=[groups[0]["GroupId"]], SubnetId=subnet_id,
            IamInstanceProfile={"Name": config.INSTANCE_PROFILE},
            UserData=render_user_data(bucket, args.region),
            BlockDeviceMappings=[
                {"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 8, "VolumeType": "gp3", "DeleteOnTermination": True}},
                {"DeviceName": "/dev/sdf", "Ebs": {"VolumeSize": args.data_gb, "VolumeType": "gp3", "DeleteOnTermination": True}},
            ],
            MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled", "HttpPutResponseHopLimit": 1},
            TagSpecifications=[config.tag_spec("instance", config.INSTANCE_NAME),
                               config.tag_spec("volume", config.INSTANCE_NAME + "-disk")])
        instance_id = launched["Instances"][0]["InstanceId"]
        say(f"  instance {instance_id} requested")

    say("  waiting for the instance to be running...")
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    ip = ensure_elastic_ip(ec2, instance_id)
    ensure_alarms(session, instance_id, args.region)

    url = f"http://{ip}/{config.CONTEXT_ROOT}/"
    say(f"\nServer: {ip}")
    say(f"SSH   : ssh -i {config.KEY_NAME}.pem ec2-user@{ip}")
    say(f"Log   : sudo tail -f /var/log/rr-bootstrap.log   (inside the server)")
    if args.no_wait:
        say(f"Not waiting. The first start takes about 6 to 10 minutes. Open {url} later.")
        return
    say(f"\nWaiting for the API (first start takes about 6 to 10 minutes)...")
    deadline = time.time() + args.wait_minutes * 60
    started = time.time()
    while time.time() < deadline:
        code = health(ip)
        if code == 200:
            say(f"\nThe API answers 200 after {int(time.time() - started)} seconds.")
            say(f"Open: {url}")
            return
        print(".", end="", flush=True)
        time.sleep(15)
    say(f"\nThe API did not answer in {args.wait_minutes} minutes.")
    show_console_tail(ec2, instance_id)
    say("\nNext: SSH into the server and run:  sudo tail -n 80 /var/log/rr-bootstrap.log")
    raise SystemExit(1)


def cmd_status(args, session):
    ec2, ssm, s3, cw = (session.client(n) for n in ("ec2", "ssm", "s3", "cloudwatch"))
    bucket = config.bucket_name(session, args.region)
    instances = config.find_instances(ec2)
    if not instances:
        say("No server exists.")
    for instance in instances:
        say(f"Server : {instance['InstanceId']} {instance['InstanceType']} state={instance['State']['Name']}")
    for address in config.find_addresses(ec2):
        ip = address["PublicIp"]
        code = health(ip)
        say(f"IP     : {ip}   API answers: {code if code else 'no answer'}")
        say(f"URL    : http://{ip}/{config.CONTEXT_ROOT}/")
    say(f"WAR now: {get_param(ssm, 'war_key', '-')}")
    say(f"WAR before: {get_param(ssm, 'war_key_previous', '-')}")
    try:
        head = s3.head_object(Bucket=bucket, Key="backups/latest.sql.gz")
        say(f"Backup : latest at {head['LastModified']:%Y-%m-%d %H:%M UTC} ({head['ContentLength'] // 1024} KB)")
    except ClientError:
        say("Backup : none yet")
    alarms = cw.describe_alarms(AlarmNamePrefix="rr-")["MetricAlarms"]
    for alarm in alarms:
        say(f"Alarm  : {alarm['AlarmName']} = {alarm['StateValue']}")


def cmd_update(args, session):
    s3, ssm = session.client("s3"), session.client("ssm")
    bucket = config.bucket_name(session, args.region)
    if not args.war:
        raise SystemExit("Use --war PATH")
    upload_war(s3, ssm, bucket, args.war)
    say("The server checks every minute and deploys it by itself. Use 'status' to follow it.")


def cmd_rollback(args, session):
    ssm = session.client("ssm")
    previous = get_param(ssm, "war_key_previous")
    current = get_param(ssm, "war_key")
    if not previous:
        raise SystemExit("There is no previous WAR to go back to.")
    put_string_param(ssm, "war_key", previous)
    put_string_param(ssm, "war_key_previous", current)
    say(f"Rolled back to {previous}. The server deploys it within a minute.")


def cmd_deployer(args, session):
    """Pushes the latest WAR deployer script to the running server and unblocks it."""
    import re
    import subprocess
    ec2 = session.client("ec2")
    addresses = config.find_addresses(ec2)
    if not addresses:
        raise SystemExit("There is no server.")
    ip = addresses[0]["PublicIp"]
    pem = os.path.join(HERE, f"{args.key_name}.pem")

    def ssh(command, data=None):
        done = subprocess.run(["ssh", "-i", pem, "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={os.devnull}",
                               "-o", "ConnectTimeout=15", "-o", "LogLevel=ERROR", f"ec2-user@{ip}", command],
                              input=data, capture_output=True, timeout=120)
        return (done.stdout + done.stderr).decode("utf-8", "replace")

    say("Deployer log on the server (last lines):")
    say(ssh("sudo journalctl -u rr-deploy --no-pager -n 12; echo; ls /var/lib/rr; sudo ls /opt"))
    text = render_user_data(config.bucket_name(session, args.region), args.region)
    script = re.search(r"cat > /usr/local/bin/rr-deploy-war <<'DEPLOYEOF'\n(.*?)DEPLOYEOF\n", text, re.S).group(1)
    ssh("sudo tee /usr/local/bin/rr-deploy-war >/dev/null && sudo chmod +x /usr/local/bin/rr-deploy-war", script.encode())
    say("Deployer script updated. Clearing any 'rejected' mark and deploying now...")
    say(ssh("sudo rm -f /var/lib/rr/rejected_war_key; sudo systemctl start rr-deploy.service; "
            "sudo journalctl -u rr-deploy --no-pager -n 6"))
    for _ in range(24):
        code = health(ip)
        if code == 200:
            say(f"The API answers 200. Open: http://{ip}/{config.CONTEXT_ROOT}/")
            return
        time.sleep(5)
    say(f"The API still answers {code}. Send me the output above.")


def cmd_stop(args, session):
    """Stops the server (disks, Elastic IP and data stay). Saves compute hours when nobody uses it."""
    ec2 = session.client("ec2")
    instances = config.find_instances(ec2, states=["pending", "running"])
    if not instances:
        say("The server is not running.")
        return
    ids = [i["InstanceId"] for i in instances]
    ec2.stop_instances(InstanceIds=ids)
    say("Stopping the server...")
    ec2.get_waiter("instance_stopped").wait(InstanceIds=ids)
    say("Stopped. The data stays on the disk. Start it again with: python deploy.py start")


def cmd_start(args, session):
    """Starts a stopped server and waits for the API."""
    ec2 = session.client("ec2")
    stopped = config.find_instances(ec2, states=["stopped", "stopping"])
    running = config.find_instances(ec2, states=["pending", "running"])
    if not stopped and not running:
        raise SystemExit("There is no server. Create it with: python deploy.py server")
    if stopped:
        ids = [i["InstanceId"] for i in stopped]
        ec2.get_waiter("instance_stopped").wait(InstanceIds=ids)
        ec2.start_instances(InstanceIds=ids)
        say("Starting the server...")
        ec2.get_waiter("instance_running").wait(InstanceIds=ids)
    addresses = config.find_addresses(ec2)
    if not addresses:
        raise SystemExit("There is no Elastic IP. Run: python deploy.py server")
    ip = addresses[0]["PublicIp"]
    if args.no_wait:
        say(f"Started. The API needs about a minute: http://{ip}/{config.CONTEXT_ROOT}/")
        return
    started = time.time()
    while time.time() - started < 300:
        if health(ip) == 200:
            say(f"The API answers 200 after {int(time.time() - started)} seconds: http://{ip}/{config.CONTEXT_ROOT}/")
            return
        print(".", end="", flush=True)
        time.sleep(5)
    say("\nThe API did not answer in 5 minutes. Check: python deploy.py status")


def main():
    parser = argparse.ArgumentParser(description="Deploy the Restaurant Review Platform on AWS")
    parser.add_argument("command", choices=["base", "server", "status", "update", "rollback", "deployer", "stop", "start"])
    parser.add_argument("--region", default=config.DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--war", help="path of the exported RestaurantReviewAPI.war")
    parser.add_argument("--schema", default=os.path.join(HERE, "..", "database", "restaurant_review_schema.sql"))
    parser.add_argument("--ssh-cidr", help="address allowed for SSH, e.g. 189.1.2.3/32 (default: your current IP)")
    parser.add_argument("--key-name", default=config.KEY_NAME)
    parser.add_argument("--instance-type", default=None)
    parser.add_argument("--arch", choices=["x86_64", "arm64"], default="x86_64")
    parser.add_argument("--data-gb", type=int, default=10, help="size of the MySQL data disk")
    parser.add_argument("--recreate", action="store_true", help="server: replace the existing server with a new one")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--wait-minutes", type=int, default=25)
    args = parser.parse_args()

    session = config.make_session(args.profile, args.region)
    handlers = {"base": cmd_base, "server": cmd_server, "status": cmd_status,
                "update": cmd_update, "rollback": cmd_rollback, "deployer": cmd_deployer,
                "stop": cmd_stop, "start": cmd_start}
    try:
        handlers[args.command](args, session)
    except ClientError as error:
        code = client_code(error)
        say(f"\nAWS answered with an error: {code}: {error.response['Error'].get('Message', '')}")
        if code in ("ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId", "AuthFailure"):
            say("The lab credentials expired. Start the lab again and copy the new credentials.")
        sys.exit(1)


if __name__ == "__main__":
    main()
