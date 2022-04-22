import json
import requests


def lambda_handler(_, __):
    try:
        url = requests.get("https://jsonplaceholder.typicode.com/users")
        data = json.loads(url.text)
    except Exception as e:
        print(e)
        raise e

    return {
        "statusCode": 200,
        "body": json.dumps(data),
    }


if __name__ == "__main__":
    lambda_handler(None, None)
