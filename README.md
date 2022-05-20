# Polarsteps Tracker
This project was created to track the journey of a colleague in the company Slack channel.

It posts the description with a single image to the channel. If there are more images they will be put in a thread under the initial message.

## Deploy
Before you deploy there are some prerequisites:
- Create an app on a Slack workspace (SlackOAuthToken)
- Create a channel on the workspace (SlackChannelId)
- Login to Polarsteps and copy the `remember_token` cookie (PolarstepsCookie)
- Find the tripId using the API at `https://api.polarsteps.com/users/byusername/{username}` (PolarstepsTripId)

The default environment is `dev`, you can specify some different env using the `Environment` parameter.

`sam build && sam deploy --parameter-overrides="PolarstepsTripId=\"{PolarstepsTripId}\" SlackOAuthToken=\"{SlackOAuthToken}\" SlackChannelId=\"{SlackChannelId}\" PolarstepsCookie=\"remember_token={PolarstepsCookie}\" Environment=\"{Environment}\"" --config-env={dev or prod, as defined in samconfig.toml}`
