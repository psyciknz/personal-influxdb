#!/usr/bin/python3
# Copyright 2022 Sam Steele
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests, sys
from config import *

if not TODOIST_ACCESS_TOKEN:
    logging.error("TODOIST_ACCESS_TOKEN not set in config.py")
    sys.exit(1)

points = []

def get_project(project_id):
	try:
		response = requests.get(f'https://api.todoist.com/sync/v9/projects/get', 
			params={'project_id': project_id},
			headers={'Authorization': f'Bearer {TODOIST_ACCESS_TOKEN}'})
		response.raise_for_status()
	except requests.exceptions.HTTPError as err:
		logging.error("HTTP request failed: %s", err)
		sys.exit(1)

	return response.json()

def get_activity(page):
	events = []
	count = -1
	offset = 0	
	while count == -1 or len(events) < count:
		logging.debug("Fetching page %s offset %s", page, len(events))
		try:
			response = requests.get(f'https://api.todoist.com/sync/v9/activity/get', 
				params={'page': page, 'offset': offset, 'limit': 100},
				headers={'Authorization': f'Bearer {TODOIST_ACCESS_TOKEN}'})
			response.raise_for_status()
		except requests.exceptions.HTTPError as err:
			logging.error("HTTP request failed: %s", err)
			sys.exit(1)

		activity = response.json()
		events.extend(activity['events'])
		count = activity['count']

	logging.info("Got %s items from Todoist", len(events))

	return events

connect(TODOIST_DATABASE)

page = 0
activity = get_activity(page)
projects = {}
for event in activity:
	if event['object_type'] == 'item':
		if event['event_type'] == 'added' or event['event_type'] == 'completed':
			project = None
			try:
				if event['parent_project_id'] in projects:
					project = projects[event['parent_project_id']]
				else:
					project = get_project(event['parent_project_id'])
					projects[event['parent_project_id']] = project
			except AttributeError as err:
				logging.warning("Unable to fetch name for project ID %s", event['parent_project_id'])

			if project != None:
				points.append({
					"measurement": event['event_type'],
					"time": event['event_date'],
					"tags": {
						"item_id": event['id'],
						"project_id": event['parent_project_id'],
						"project_name": project['project']['name'],
					},
					"fields": {
						"content": event['extra_data']['content']
					}
				})

write_points(points)
