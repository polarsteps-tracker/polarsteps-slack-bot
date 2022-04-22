import os
import json
import time
import logging

import requests
import boto3

username = os.environ.get('POLARSTEPS_USERNAME')
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


def lambda_handler(_, __):
    try:
        last_execution_time = get_last_execution_time()
        current_time = time.time()

        url = requests.get(f"https://api.polarsteps.com/users/byusername/{username}")
        data = json.loads(url.text)
        trips = data['alltrips']
        steps = trips[0]['all_steps']  # TODO: find correct trip
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
        temp = []
        for step in new_steps:
            logger.debug(f"Processing step {step['id']}")
            date_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(step['creation_time']))
            location = f"{step['location']['name']}({step['location']['country_code']})"
            description = step['description']
            if 'media' in step:
                images = list(map(lambda m: m['large_thumbnail_path'], step['media']))
            else:
                images = []
            logger.info(f"{date_time} - {location} - {description}")
            logger.debug(images)
            temp.append({
                'date_time': date_time,
                'location': location,
                'description': description,
                'images': images
            })

        set_last_execution_time(current_time)

        return {
            "statusCode": 200,
            "body": json.dumps(temp),
        }
    except Exception as e:
        logger.error(e)
        raise e
