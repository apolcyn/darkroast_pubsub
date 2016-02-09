# Copyright 2015 Google Inc.
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

from flask import current_app
from gcloud import datastore
import json
from polypaths_planar_override import Point

builtin_list = list

def init_app(app):
    pass


def get_client():
    return datastore.Client(
        dataset_id=current_app.config['DATASTORE_DATASET_ID'])


def from_datastore(entity):
    """Translates Datastore results into the format expected by the
    application.

    Datastore typically returns:
        [Entity{key: (kind, id), prop: val, ...}]

    This returns:
        {id: id, prop: val, ...}
    """
    if not entity:
        return None
    if isinstance(entity, builtin_list):
        entity = entity.pop()

    entity['id'] = entity.key.id
    return entity


def list(limit=10, cursor=None):
    ds = get_client()
    query = ds.query(kind='Book', order=['title'])
    it = query.fetch(limit=limit, start_cursor=cursor)
    entities, more_results, cursor = it.next_page()
    entities = builtin_list(map(from_datastore, entities))
    return entities, cursor if len(entities) == limit else None

def get_all_locations_from_source_id(source_id):
    out = []
    ds = get_client()
    query = ds.query(kind='LocationUpdate')
    query.add_filter(property_name='sourceId', operator='=', value=source_id)
    for update in sorted(map(from_datastore, query.fetch()), key=lambda x:x['updateTime']):
        out.append({'lat': update['latitude'], 'lng': update['longitude']})
    return out

def store_partitioned_trajectories(partitioned_line_segs, key_id=0):
    ds = get_client()
    out = []
    for segment in partitioned_line_segs:
        out.append({'lat': segment.start.x, 'lng': segment.start.y})
        out.append({'lat': segment.end.x, 'lng': segment.end.y})
    key = ds.key('PartitionedTrajectories', key_id)
    entity = datastore.Entity(key=key, exclude_from_indexes=['segments'])
    entity.update({'segments': json.dumps(out)})
    ds.put(entity)
    
def get_partitioned_trajectories(key_id=0):
    ds = get_client()
    key = ds.key('PartitionedTrajectories', key_id)
    results = from_datastore(ds.get(key))
    return json.loads(results['segments'])

def store_filtered_trajectories(filtered_trajectories):
    ds = get_client()
    out = []
    for single_traj in filtered_trajectories:
        out.append(map(lambda p: {'lat':p.x, 'lng':p.y}, single_traj))
    key = ds.key('FilteredTrajectories')
    entity = datastore.Entity(key=key, exclude_from_indexes=['trajectories'])
    entity.update({'trajectories': json.dumps(out)})
    ds.put(entity)
    
def get_filtered_trajectories():
    ds = get_client()
    query = ds.query(kind='FilteredTrajectories')
    for entity in map(from_datastore, query.fetch(limit=1)):
        trajectories = json.loads(entity['trajectories'])
        break
    return {'0': trajectories}

def get_all_location_updates():
    out = {}
    ds = get_client()
    query = ds.query(kind='LocationUpdate')
    query.add_filter(property_name='sourceId', operator='=', value=0)
    location_update_roots = query.fetch()
    for update_root in map(from_datastore, location_update_roots):
        out[update_root['id']] = \
        [get_all_locations_from_source_id(source_id=update_root['id'])]
    return out

def list_by_user(user_id, limit=10, cursor=None):
    ds = get_client()
    query = ds.query(
        kind='Book',
        filters=[
            ('createdById', '=', user_id)
        ]
    )
    it = query.fetch(limit=limit, start_cursor=cursor)
    entities, more_results, cursor = it.next_page()
    entities = builtin_list(map(from_datastore, entities))
    return entities, cursor if len(entities) == limit else None

def read(id):
    ds = get_client()
    key = ds.key('Book', int(id))
    results = ds.get(key)
    return from_datastore(results)


def update(data, id=None):
    ds = get_client()
    if id:
        key = ds.key('Book', int(id))
    else:
        key = ds.key('Book')

    entity = datastore.Entity(
        key=key,
        exclude_from_indexes=['description'])

    entity.update(data)
    ds.put(entity)
    return from_datastore(entity)


create = update


def delete(id):
    ds = get_client()
    key = ds.key('Book', int(id))
    ds.delete(key)
