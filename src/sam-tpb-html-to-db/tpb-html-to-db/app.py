import json
import boto3, botocore
from bs4 import BeautifulSoup
import pandas as pd
import hashlib
from datetime import datetime


def extract_values_from_li(li):
    spans = li.find_all("span")
    keys = [sp.attrs["class"][-1].replace("item-", "") for sp in spans]
    values = [sp.text.replace("\xa0", "") for sp in spans]
    data = dict(zip(keys, values))

    # Links
    links = [sp.find("a")["href"] for sp in spans if sp.find("a")]
    data["torrent_url"] = "https://thepiratebay.org" + links[1]

    # Icons
    icons = [
        img["src"].rsplit("/")[-1].split(".gif")[0]
        for img in torrent_list[0].findAll("img")
    ]
    data["icons"] = icons

    # Data cleanup
    types = data["type"].split(" > ")
    data["type_a"], data["type_b"] = types[0], types[1]
    del data["type"]

    # Convert size to the same units (Megabytes)
    size = data["size"]
    if "TiB" in size:
        size = float(size.replace("TiB", "")) * 1024 * 1024
    elif "GiB" in size:
        size = float(size.replace("GiB", "")) * 1024
    elif "MiB" in size:
        size = float(size.replace("MiB", ""))
    elif "KiB" in size:
        size = float(size.replace("KiB", "")) / 1024
    else:
        size = float(size.replace("B", "")) / (1024**2)
    data["megabytes"] = int(size)
    del data["size"]

    data["seed"] = int(data["seed"])
    data["leech"] = int(data["leech"])

    timestamp_str = file_name.split("tbp_top100_")[1].split(".html")[0]
    data["timestamp"] = int(
        datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").timestamp()
    )

    # Make a uid key in data from a hash of everything else in the data dict
    hashable_string = data["torrent_url"] + str(data["timestamp"])
    data["uid"] = hashlib.md5(hashable_string.encode()).hexdigest()

    return data


def lambda_handler(event, context):
    # When running locally with SAM, AWS profile info may not be accessible
    # Hence, we use the default session
    session = boto3.Session()
    s3 = session.client("s3")
    bucket_name = "tpb-snapshots-html"
    # Get the data drop
    df_list = []
    try:
        objects = s3.list_objects(Bucket=bucket_name)["Contents"]
    except KeyError:
        return {"errorMessage": "Bucket is empty"}
    for obj in objects:
        file_name = obj["Key"]
        if file_name.endswith(".html"):
            file_obj = s3.get_object(Bucket=bucket_name, Key=file_name)
            file_content = file_obj["Body"].read()

            # Soupify
            soup = BeautifulSoup(file_content, "html.parser")
            torrent_list = soup.find_all("li", class_="list-entry")

            df = pd.DataFrame([extract_values_from_li(li) for li in torrent_list])
            df["timestamp"] = (
                pd.to_datetime(df.timestamp, format="%Y-%m-%d_%H-%M").astype(int)
                / 10**9
            ).astype(int)
            df_list.append(df)

    df = pd.concat(df_list, ignore_index=True)

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("tpb-top100-ts")

    for index, row in df.iterrows():
        try:
            table.put_item(
                Item={
                    "uid": row["uid"],
                    "timestamp": row["timestamp"],
                    "data": row.to_dict(),
                },
                ConditionExpression="attribute_not_exists(uid)",
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                print(f"Item with uid {row['uid']} already exists.")
            else:
                raise

    # Delete the objects from s3 after processing
    for obj in s3.list_objects(Bucket=bucket_name)["Contents"]:
        s3.delete_object(Bucket=bucket_name, Key=obj["Key"])

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "New data posted to DynamoDB (probably)",
            }
        ),
    }
