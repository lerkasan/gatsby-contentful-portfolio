from pulumi import export, Output
from pulumi_aws import s3, cloudfront, route53, acm
import json

WEBSITE_DOMAIN_NAME = "lerkasan.de"
WWWROOT_BUCKET_NAME = WEBSITE_DOMAIN_NAME + "-wwwroot"
LOGS_BUCKET_NAME = WEBSITE_DOMAIN_NAME + "-logs"
CLOUDFRONT_DISTRIBUTION_NAME =WEBSITE_DOMAIN_NAME + "-CDN"


def public_access_policy_for_s3website_bucket(bucket_name):
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
        bucket=bucket_name,
        acl="public-read",
        website=s3.BucketWebsiteArgs(
            index_document="index.html",
            error_document="404.html",
        ),
        tags={
             "Website": WEBSITE_DOMAIN_NAME,
             "Environment": "dev",
           },
    )
    bucket_id = bucket.id
    bucket_policy = s3.BucketPolicy(bucket_name + "-bucket-policy",
                                    bucket=bucket_id,
                                    policy=bucket_id.apply(public_access_policy_for_s3website_bucket))
    return bucket


def create_cloudfront_distribution_for_s3website(wwwroot_bucket, logs_bucket, ssl_certificate):
    s3_distribution = cloudfront.Distribution(CLOUDFRONT_DISTRIBUTION_NAME,
        origins=[cloudfront.DistributionOriginArgs(
            domain_name=wwwroot_bucket.bucket_regional_domain_name,
            origin_id=wwwroot_bucket.id,
        )],
        enabled=True,
        is_ipv6_enabled=True,
        comment="Distribution for the bucket " + WWWROOT_BUCKET_NAME,
        default_root_object="index.html",
        logging_config=cloudfront.DistributionLoggingConfigArgs(
            include_cookies=False,
            bucket=logs_bucket.bucket_regional_domain_name,
        ),
        aliases=[
            WEBSITE_DOMAIN_NAME,
        ],
        default_cache_behavior=cloudfront.DistributionDefaultCacheBehaviorArgs(
            allowed_methods=[
                "DELETE",
                "GET",
                "HEAD",
                "OPTIONS",
                "PATCH",
                "POST",
                "PUT",
            ],
            cached_methods=[
                "GET",
                "HEAD",
            ],
            target_origin_id=wwwroot_bucket.id,
            forwarded_values=cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
                query_string=False,
                cookies=cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                    forward="none",
                ),
            ),
            viewer_protocol_policy="redirect-to-https",
            min_ttl=0,
# Default TTL value of cache was intentionally decreased from 1 hour (default_ttl=3600) to 2 minutes
# to make it easier to notice that after the CI workflow is run all content changes from Contentful CMS website
# will be actually deployed to the S3+Cloudfront website
            default_ttl=120,
            max_ttl=86400,
        ),

        restrictions=cloudfront.DistributionRestrictionsArgs(
            geo_restriction=cloudfront.DistributionRestrictionsGeoRestrictionArgs(
                restriction_type="none",
            ),
        ),
        tags={
            "Website": WEBSITE_DOMAIN_NAME,
            "Environment": "dev",
        },
        viewer_certificate=cloudfront.DistributionViewerCertificateArgs(
            acm_certificate_arn=ssl_certificate.arn,
            ssl_support_method='sni-only',
        ))
    return s3_distribution


def create_alias_record(alias_domain, distribution):
    zone_id = route53.get_zone(name=alias_domain).id
    return route53.Record(alias_domain,
        name="",
        zone_id=zone_id,
        type='A',
        aliases=[
            route53.RecordAliasArgs(
                name=distribution.domain_name,
                zone_id=distribution.hosted_zone_id,
                evaluate_target_health=True,
            )]
        )

logs_bucket = s3.Bucket(LOGS_BUCKET_NAME,
                    bucket=LOGS_BUCKET_NAME,
                    acl="private")

wwwroot_bucket = create_s3website_bucket(WWWROOT_BUCKET_NAME)
ssl_certificate = acm.get_certificate(domain=WEBSITE_DOMAIN_NAME, statuses=["ISSUED"])
s3_distribution = create_cloudfront_distribution_for_s3website(wwwroot_bucket, logs_bucket, ssl_certificate)
create_alias_record(WEBSITE_DOMAIN_NAME, s3_distribution)


export("s3_bucket_url", Output.concat("s3://", wwwroot_bucket.bucket))
export("s3_bucket_website_endpoint", wwwroot_bucket.website_endpoint)
export("cloudfront_domain_name", s3_distribution.domain_name)
export("route53_endpoint", f"https://{WEBSITE_DOMAIN_NAME}/")
