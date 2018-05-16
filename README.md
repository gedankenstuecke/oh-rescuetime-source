# The OH Moves integration

[![Build Status](https://travis-ci.org/OpenHumans/oh-moves-source.svg?branch=master)](https://travis-ci.org/OpenHumans/oh-moves-soure)

This repository provides a `Django` application that interfaces both with the `Open Humans` API and the `Moves` API to collect GPS track data from `Moves` and uploading it into `Open Humans`. It is based on the https://github.com/OpenHumans/oh-data-demo-template repository.

For a user the workflow is the following:

1. User goes to the website provided by this repo
2. A user signs up/signs in with Open Humans and authorizes the `Moves` integration on `Open Humans`
3. This redirects the user back to this Moves-integration website
4. The user is redirected starts the authorization with `Moves`. For this they are redirected to the Moves page
5. After a user has authorized both `Open Humans` & `Moves` their `Moves` data will be requested and ultimately saved as a file in Open Humans.
6. Regular updates of the data should be automatically triggered to keep the data on Open Humans up to date.

Getting the data from `Moves` and uploading it to Open Humans has a couple of challenges:
1. The `Moves` API uses rate limits, which need to be respected and going over the rate limit would not yield more data but just errors
2. Getting all the data from `Moves` takes a while, not only because of the rate limits, but also because it can be a lot of data
3. We want to regularly update data and take into account data we already did upload to Open Humans.

For this reason this application makes good use of background tasks with `Celery` and the Python module `requests_respectful`, which keeps track of API limits by storing limits in a `redis` database. As `redis` is already used for `Celery` as well this does not increase the number of non-python dependencies.

## setup for requests_respectful
The settings for `requests_respectful` can be found in `demotemplate/settings.py`.

```
rr = RespectfulRequester()
rr.register_realm("moves", max_requests=60, timespan=60)
```
By registering a `realm` we set up a namespace for the moves requests and specify that at max. 60 requests per 60 seconds can be made. If we would make an additional request this would yield a `RequestsRespectfulRateLimitedError`.

## setup for Celery
The settings for Celery can be found in `datauploader/celery.py`. These settings apply globally for our application. The Celery task itself can be found in `datauploader/tasks.py`. The main task for requesting & processing the moves data is `process_rescuetime()` in that file.

## `process_rescuetime()`
This task solves both the problem of hitting API limits as well as the import of existing data.
The rough workflow is

```
get_existing_moves(…)
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

### `get_existing_moves`
This step just checks whether there is already older `Moves` data on Open Humans. If there is data
it will download the old data and import it into our current workflow. This way we already know which dates we don't have to re-download from `Moves` again.

### `get_start_date`
This function checks what the last dates are for which we have downloaded data before. This tells us from which date in the past we have to start downloading more data.

### `remove_partial_data`
The Moves download works on a ISO-week basis. E.g. we request data for `Calendar Week 18`. But if we request week 18 on a Tuesday we will miss out on all of the data from Wednesday to Sunday. For that reason we make sure to drop the last week during which we already downloaded data and re-download that completely.

### getting more data.
Here we just run a while loop over our date range beginning from our `start_date` until we hit `today`.

### `except`
When we hit the Moves API rate limit we can't make any more requests and the exception will be raised. When this happens we put a new `process_rescuetime` for this user into our `Celery` queue. With the `countdown` parameter we can specify for how long the job should at least be idle before starting again. Ultimately this serves as a cooldown period so that we are allowed new API calls to the `Moves API`.

### `finally: replace_moves`
No matter whether we hit the API limit or not: We always want to upload the new data we got from the Moves API back to Open Humans. This way we can incrementally update the data on Open Humans, even if we regularly hit the API limits.

### Example flow for `process_rescuetime`
1. We want to download new data for user A and `get_existing_moves` etc. tells us we need data for the weeks 01-10.
2. We start our API calls and in Week 6 we hit the API limit. We now enqueue a new `process_rescuetime()` task with `Celery`.
3. We then upload our existing data from week 1-5 to Open Humans. This way a user has at least some data already available
4. After the countdown has passed our in `2` enqueued `process_rescuetime` task starts.
5. This new task downloads the data from Open Humans and finds it already has data for weeks 1-5. So our new task only needs to download the data for week 5-10. It can now start right in week 5 and either finish without hitting a limit again, or it will at least make it through some more weeks before crashing again, which in turn will trigger yet another new `process_rescuetime` task for later.

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
