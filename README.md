# The OH RescueTime integration

[![Build Status](https://travis-ci.org/OpenHumans/oh-rescuetime-source.svg?branch=master)](https://travis-ci.org/OpenHumans/oh-rescuetime-soure)

This repository provides a `Django` application that interfaces both with the `Open Humans` API and the `RescueTime` API to collect productivity data from `RescueTime` and uploading it into `Open Humans`. It is based on the https://github.com/OpenHumans/oh-data-demo-template repository.

For a user the workflow is the following:

1. User goes to the website provided by this repo
2. A user signs up/signs in with Open Humans and authorizes the `Rescuetime` integration on `Open Humans`
3. This redirects the user back to this RescueTime integration website
4. The user is redirected & starts the authorization with `RescueTime`. For this they are redirected to the RescueTime page
5. After a user has authorized both `Open Humans` & `RescueTime` their `RescueTime` data will be requested and ultimately saved as a file in Open Humans.
6. Regular updates of the data should be automatically triggered to keep the data on Open Humans up to date.

Getting the data from `RescueTime` and uploading it to Open Humans has a couple of challenges:
1. Getting all the data from `RescueTime` takes a while, as it can be a lot of data
2. We want to regularly update data and take into account data we already did upload to Open Humans.
3. We don't know what the first date is a person has used RescueTime, which is why we have to start on `2008-01-01` as a naive start date for when `RescueTime` was started.

For these reasons this application makes good use of background tasks with `Celery`. As `RescueTime` doesn't advertise API limits we don't care for these for now. 

## setup for Celery
The settings for Celery can be found in `datauploader/celery.py`. These settings apply globally for our application. The Celery task itself can be found in `datauploader/tasks.py`. The main task for requesting & processing the moves data is `process_rescuetime()` in that file.

## `process_rescuetime()`
This task solves both the problem of hitting API limits as well as the import of existing data.
The rough workflow is

```
get_existing_rescuetime(…)
get_start_date(…)
remove_partial_data(…)
try:
  while *no_error* and still_new_data:
    get more data
except:
  process_rescuetime.async_apply(…,countdown=wait_period)
finally:
  replace_moves(…)
```

### `get_existing_rescuetime`
This step just checks whether there is already older `RescueTime` data on Open Humans. If there is data
it will download the old data and import it into our current workflow. This way we already know which dates we don't have to re-download from `RescueTime` again.

### `get_start_date`
This function checks what the last dates are for which we have downloaded data before. This tells us from which date in the past we have to start downloading more data.

### `remove_partial_data`
With the `get_start_date` function we found the last day for which we already had observed data. We then just remove this day's data from our existing data hash to make sure we get the latest numbers also for this day.. E.g. we request data for `today` at 2pm we will miss out on 10h worth of data for `today`. But if we request `today` naively a second time we would have a data duplication. For that reason we make sure to drop `today` from the already downloaded data and re-download that completely.

### getting more data.
Here we just run a while loop over our date range beginning from our `start_date` until we hit `today`.

### `except`
When things go wrong an exception will be raised. When this happens we put a new `process_rescuetime` task for this user into our `Celery` queue. With the `countdown` parameter we can specify for how long the job should at least be idle before starting again. 

### `finally: replace_moves`
No matter whether we hit the API limit or not: We always want to upload the new data we got from the Moves API back to Open Humans. This way we can incrementally update the data on Open Humans, even if we regularly hit the API limits.

## Doing automatic updates of the Moves data
This can be done by regularly enqueuing `process_rescuetime` tasks with `Celery`. As `Heroku` does not offer another cheap way of doing it we can use a `management task` for this that will be called daily by the `heroku scheduler`.

This Management task lives in `main/management/commands/update_data.py`. Each time it is called it iterates over all `Moves` user models and checks when the last update was performed. If the last update happened more than 4 days ago it will put a `process_rescuetime` task into the `Celery` queue.

## Folder structure

- `datauploader` contains both
  - the celery settings in `celery.py`
  - and the actual `celery tasks` in `tasks.py`
- `demotemplate`contains
  - the general app's `settings.py`
- `main` contains the
  - `views.py` for the actual views
  - the `templates/` for the views
  - the `urls.py` for routing
  - the `models.py` that describe the `Moves User Model`
  - the `tests/` for the whole application
  - the `management/` commands
- `open_humans` contains
  - the `Open Humans user model`
