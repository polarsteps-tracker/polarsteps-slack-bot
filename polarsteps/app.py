import json
import logging
import os
import time
from dataclasses import dataclass

import boto3
import requests

ENVIRONMENT = os.environ.get('ENVIRONMENT')
SLACK_OAUTH_TOKEN = os.environ.get('SLACK_OAUTH_TOKEN')
SLACK_CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')
POLARSTEPS_TRIP_ID = os.environ.get('POLARSTEPS_TRIP_ID')
POLARSTEPS_COOKIE = os.environ.get('POLARSTEPS_COOKIE')

client = boto3.client('ssm')

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


@dataclass
class Step:
    user: str
    datetime: str
    country: str
    place: str
    description: str
    image_urls: [str]


def get_last_execution_time():
    try:
        response = client.get_parameter(
            Name=f"/polarsteps/lastExecutionTime/{ENVIRONMENT}"
        )
        return float(response['Parameter']['Value'])
    except Exception as e:
        logger.error(e)
        raise e


def set_last_execution_time(time):
    try:
        client.put_parameter(
            Name=f"/polarsteps/lastExecutionTime/{ENVIRONMENT}",
            Value=str(time),
            Type='String',
            Overwrite=True
        )
    except Exception as e:
        logger.error(e)
        raise e


def send_slack_message(step: Step):
    url = "https://slack.com/api/chat.postMessage"
    data = {
        "channel": SLACK_CHANNEL_ID,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{step.user} was in {step.place} ({step.country})",
                    "emoji": True
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": step.description
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Where*\n{step.place} ({step.country})"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*When*\n{step.datetime}"
                    }
                ]
            }
        ]
    }

    if len(step.image_urls) > 0:
        data["blocks"].append({
            "type": "image",
            "image_url": step.image_urls[0],
            "alt_text": "no alt text"
        })

    logger.debug(data)

    try:
        response = requests.post(url, json=data, headers={
            "Authorization": f"Bearer {SLACK_OAUTH_TOKEN}"
        })
        logger.debug(response.text)

        thread = response.json()['ts']

        if len(step.image_urls) > 1:
            for image_url in step.image_urls[1:]:
                reply_data = {
                    "channel": SLACK_CHANNEL_ID,
                    "thread_ts": thread,
                    "blocks": [{
                        "type": "image",
                        "image_url": image_url,
                        "alt_text": "no alt text"
                    }],
                }

                response = requests.post(url, json=reply_data, headers={
                    "Authorization": f"Bearer {SLACK_OAUTH_TOKEN}"
                })
            logger.debug(response.text)
    except Exception as e:
        logger.error(e)
        raise e


def lambda_handler(_, __):
    try:
        last_execution_time = get_last_execution_time()

        data = json.loads(
            requests.get(f"https://api.polarsteps.com/trips/{POLARSTEPS_TRIP_ID}",
                         headers={"Cookie": POLARSTEPS_COOKIE}).text
        )

        user = data['user']
        full_name = user['first_name'] + ' ' + user['last_name']
        steps = [step for step in data['all_steps'] if 'creation_time' in step and step['creation_time'] > last_execution_time]
        steps.sort(key=lambda x: x['creation_time'])

        if len(steps) == 0:
            logger.info("No new steps to process")
            return {"statusCode": 200, "body": json.dumps([])}

        print(f"Processing {len(steps)} new steps")
        for step in steps:
            logger.debug(f"Processing step {step['id']}")
            logger.debug(step)

            date_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(step['creation_time']))
            description = step['description']
            images = ([media['large_thumbnail_path'] for media in step['media']]) if 'media' in step else []
            step_model = Step(full_name, date_time, step['location']['country_code'], step['location']['name'],
                              description, images)

            logger.info(f"{step_model.user} on {step_model.datetime} at {step_model.place} ({step_model.country})")
            logger.debug(step_model)

            send_slack_message(step_model)

        set_last_execution_time(steps[-1]['creation_time'])

        logger.info("Done")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": f"Processed {len(steps)} new steps"
            })
        }

    except Exception as e:
        logger.error(e)
        raise e
