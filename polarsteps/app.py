import os
import json
import time
import logging
from dataclasses import dataclass

import requests
import boto3

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
    location: str
    description: str
    image_urls: [str]


def get_last_execution_time():
    try:
        response = client.get_parameter(
            Name='/polarsteps/lastExecutionTime'
        )
        return float(response['Parameter']['Value'])
    except Exception as e:
        logger.error(e)
        raise e


def set_last_execution_time(time):
    try:
        client.put_parameter(
            Name='/polarsteps/lastExecutionTime',
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
                    "text": f"{step.user} is now in {step.location} - {step.datetime}",
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
        ]
    }

    if len(step.image_urls) > 0:
        data['blocks'].append({
            "type": "divider"
        })

    for image_url in step.image_urls:
        data['blocks'].append({
            "type": "image",
            "image_url": image_url,
            "alt_text": "no alt text"
        })

    logger.debug(data)

    try:
        response = requests.post(url, json=data, headers={
            "Authorization": f"Bearer {SLACK_OAUTH_TOKEN}"
        })
        logger.debug(response.text)
    except Exception as e:
        logger.error(e)
        raise e


def lambda_handler(_, __):
    try:
        last_execution_time = get_last_execution_time()
        current_time = time.time()

        data = json.loads(
            requests.get(f"https://api.polarsteps.com/trips/{POLARSTEPS_TRIP_ID}", headers={"Cookie": POLARSTEPS_COOKIE}).text
        )

        user = data['user']
        full_name = user['first_name'] + ' ' + user['last_name']
        steps = [step for step in data['all_steps'] if 'creation_time' in step and step['creation_time'] >= last_execution_time]
        steps.sort(key=lambda x: x['creation_time'])

        if len(steps) == 0:
            logger.info("No new steps to process")
            return {"statusCode": 200, "body": json.dumps([])}

        print(f"Processing {len(steps)} new steps")
        for step in steps:
            logger.debug(f"Processing step {step['id']}")
            logger.debug(step)

            date_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(step['creation_time']))
            location = f"{step['location']['name']} ({step['location']['country_code']})"
            description = step['description']
            images = ([media['large_thumbnail_path'] for media in step['media']]) if 'media' in step else []
            step_model = Step(full_name, date_time, location, description, images)

            logger.info(f"{step_model.user} on {step_model.datetime} at {step_model.location}")
            logger.debug(step_model)

            send_slack_message(step_model)

        set_last_execution_time(current_time)

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
