from pulumi_aws import s3
from pulumi import export
import json

BUCKET_NAME = "gatsby-contentful"

def public_read_policy_for_bucket(bucket_name):
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket_name}/*",
            ]
        }]
    })


def create_s3website_bucket(bucket_name):
    bucket = s3.Bucket(bucket_name,
        acl="public-read",
        website=s3.BucketWebsiteArgs(
            index_document="index.html",
            error_document="404.html",
        ))
    bucket_id = bucket.id
    bucket_policy = s3.BucketPolicy("bucket-policy",
        bucket=bucket_name,
        policy=bucket_id.apply(public_read_policy_for_bucket))
    export('bucket_id', bucket_id)
    export('website_url', bucket.website_endpoint)


create_s3website_bucket(BUCKET_NAME)
