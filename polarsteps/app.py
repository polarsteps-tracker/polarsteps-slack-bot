import os
import json
import time
import logging

import requests
import boto3

SLACK_OAUTH_TOKEN = os.environ.get('SLACK_OAUTH_TOKEN')
SLACK_CHANNEL_ID = os.environ.get('SLACK_CHANNEL_ID')
POLARSTEPS_TRIP_ID = os.environ.get('POLARSTEPS_TRIP_ID')
POLARSTEPS_COOKIE = os.environ.get('POLARSTEPS_COOKIE')

client = boto3.client('ssm')

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


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


def send_slack_message(message, images):
    try:
        url = "https://slack.com/api/chat.postMessage"
        data = {
            "channel": SLACK_CHANNEL_ID,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        }

        if len(images) > 0:
            for image in images:
                data['blocks'].append({
                    "type": "section",
                    "accessory": {
                        "type": "image",
                        "image_url": image,
                    }
                })

        requests.post(url, data, headers={
            "Authorization": f"Bearer {SLACK_OAUTH_TOKEN}"
        })
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
        steps = [step for step in data['all_steps'] if 'creation_time' in step]

        new_steps = []
        for step in steps:
            if step['creation_time'] < last_execution_time:
                logger.debug(f"Skipping step {step['id']}, because it was created before {last_execution_time}")
                continue
            new_steps.append(step)

        if len(new_steps) == 0:
            logger.info("No new steps to process")
            return {
                "statusCode": 200,
                "body": json.dumps([])
            }

        print(f"Processing {len(new_steps)} new steps")
        new_steps.sort(key=lambda x: x['creation_time'])
        for step in new_steps:
            logger.debug(f"Processing step {step['id']}")
            logger.debug(step)
            date_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(step['creation_time']))
            location = f"{step['location']['name']} ({step['location']['country_code']})"
            description = step['description']
            if 'media' in step:
                images = list(map(lambda m: m['large_thumbnail_path'], step['media']))
            else:
                images = []
            logger.info(f"{date_time} - {location} - {description}")
            logger.debug(images)
            message = f"{full_name} is now in {location}\n"
            message += f"{date_time}\n"
            message += f"{description}\n"
            send_slack_message(message, images)

        set_last_execution_time(current_time)

        logger.info("Done")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": f"Processed {len(new_steps)} new steps"
            })
        }

    except Exception as e:
        logger.error(e)
        raise e
