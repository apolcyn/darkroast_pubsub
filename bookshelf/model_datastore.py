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

CLUSTERS_TABLE = 'Clusters'
CLUSTERS_DEFAULT_ID = 1
CLUSTERS_ATTR_NAME = 'clusters'

PARTITIONED_TRAJ_TABLE = CLUSTERS_TABLE
PARTITION_TRAJ_DEFAULT_ID = 2
PARTITION_TRAJ_ATTR_NAME = 'segments'

RESULTS_TABLE_NAME = 'FilteredTrajectories'
RESULTS_ATTR_NAME = 'trajectories'
RESULTS_DEFAULT_ID = 3

NEIGHBOR_COUNTS_TABLE = 'NeighborCounts'
NEIGHBOR_COUNTS_DEFAULT_ID = 1
NEIGHBOR_COUNTS_ATTR_NAME = 'neighbor_counts'

RAW_TRAJECTORY_TABLE = 'RawTrajectoryTable'
RAW_TRAJECTORY_TRAJ_ATTR_NAME = 'trajectory'
RAW_TRAJECTORY_DRAWN_ATTR_NAME = 'drawn'
RAW_TRAHECTORY_DEFAULT_ID = 1

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

def store_new_trajectory_update(new_trajectory, drawn_by_hand):
    ds = get_client()
    key = ds.key(RAW_TRAJECTORY_TABLE)
    entity = datastore.Entity(key=key, \
                              exclude_from_indexes=[RAW_TRAJECTORY_TRAJ_ATTR_NAME, \
                                                    RAW_TRAJECTORY_DRAWN_ATTR_NAME])
    entity.update({RAW_TRAJECTORY_TRAJ_ATTR_NAME: json.dumps(new_trajectory), \
                   RAW_TRAJECTORY_DRAWN_ATTR_NAME: drawn_by_hand})
    ds.put(entity)
    
def get_raw_trajectories():
    ds = get_client()
    query = ds.query(kind=RAW_TRAJECTORY_TABLE)
    out = []
    for traj in map(from_datastore, query.fetch()):
        out.append(json.loads(traj[RAW_TRAJECTORY_TRAJ_ATTR_NAME]))
    return out

def get_all_locations_from_source_id(source_id):
    out = []
    ds = get_client()
    query = ds.query(kind='LocationUpdate')
    query.add_filter(property_name='sourceId', operator='=', value=source_id)
    for update in sorted(map(from_datastore, query.fetch()), key=lambda x:x['updateTime']):
        out.append({'lat': update['latitude'], 'lng': update['longitude']})
    return out

def store_partitioned_trajectories(partitioned_line_segs, key_id=PARTITION_TRAJ_DEFAULT_ID):
    ds = get_client()
    out = []
    if len(partitioned_line_segs) == 0:
        raise ValueError("length of partitioned line segs is " + \
                         str(len(partitioned_line_segs)))
        
    for segment in map(lambda t: t.line_segment, partitioned_line_segs):
        out.append([{'lat': segment.start.x, 'lng': segment.start.y}, \
                    {'lat': segment.end.x, 'lng': segment.end.y}])
    key = ds.key(PARTITIONED_TRAJ_TABLE, key_id)
    entity = datastore.Entity(key=key, exclude_from_indexes=[PARTITION_TRAJ_ATTR_NAME])
    entity.update({PARTITION_TRAJ_ATTR_NAME: json.dumps(out)})
    ds.put(entity)
    
def filter_trajectories(trajectories):
    out = []
    for source_id in trajectories:
        traj_list = trajectories[source_id]
        for traj in traj_list:
            out.append(map(lambda x: Point(x['lat'], x['lng']), traj))
    return out
    
def get_partitioned_trajectories(key_id=PARTITION_TRAJ_DEFAULT_ID):
    ds = get_client()
    key = ds.key(PARTITIONED_TRAJ_TABLE, key_id)
    results = from_datastore(ds.get(key))
    return json.loads(results[PARTITION_TRAJ_ATTR_NAME])

def store_clusters(clusters, key_id=CLUSTERS_DEFAULT_ID):
    ds = get_client()
    key = ds.key(CLUSTERS_TABLE, key_id)
    entity = datastore.Entity(key=key, exclude_from_indexes=[CLUSTERS_ATTR_NAME])
    out = []
    if len(clusters) == 0:
        return
        #raise ValueError("lenth of clusters is " + str(len(clusters)))
    
    for single_cluster in clusters:
        in_cluster_list = []
        for seg in map(lambda x: x.line_segment, single_cluster.get_trajectory_line_segments()):
            in_cluster_list.append([{'lat': seg.start.x, 'lng': seg.start.y}, \
                                    {'lat': seg.end.x, 'lng': seg.end.y}])
        out.append(in_cluster_list)
    entity.update({CLUSTERS_ATTR_NAME: json.dumps(out)})
    ds.put(entity)
    
def store_line_segment_neighbor_counts(line_segments, key_id=NEIGHBOR_COUNTS_DEFAULT_ID):
    ds = get_client()
    key = ds.key(NEIGHBOR_COUNTS_TABLE, key_id)
    entity = datastore.Entity(key=key, exclude_from_indexes=[NEIGHBOR_COUNTS_ATTR_NAME])
    out = map(lambda seg: seg.get_num_neighbors(), line_segments)
    entity.update({NEIGHBOR_COUNTS_ATTR_NAME: json.dumps(out)})
    ds.put(entity)
    
def get_line_segment_neighbor_counts(key_id=NEIGHBOR_COUNTS_DEFAULT_ID):
    ds = get_client()
    key = ds.key(NEIGHBOR_COUNTS_TABLE, NEIGHBOR_COUNTS_DEFAULT_ID)
    results = from_datastore(ds.get(key))
    return json.loads(results[NEIGHBOR_COUNTS_ATTR_NAME])
    
def get_clusters(key_id=CLUSTERS_DEFAULT_ID):
    ds = get_client()
    key = ds.key(CLUSTERS_TABLE, key_id)
    results = from_datastore(ds.get(key))
    return json.loads(results[CLUSTERS_ATTR_NAME])

def store_filtered_trajectories(filtered_trajectories, key_id=RESULTS_DEFAULT_ID):
    ds = get_client()
    out = []
    for single_traj in filtered_trajectories:
        out.append(map(lambda p: {'lat':p.x, 'lng':p.y}, single_traj))
    key = ds.key(RESULTS_TABLE_NAME, key_id)
    entity = datastore.Entity(key=key, exclude_from_indexes=[RESULTS_ATTR_NAME])
    entity.update({RESULTS_ATTR_NAME: json.dumps(out)})
    ds.put(entity)
    
def get_filtered_trajectories(key_id=RESULTS_DEFAULT_ID):
    ds = get_client()
    key = ds.key(RESULTS_TABLE_NAME, key_id)
    trajectories = from_datastore(ds.get(key))
    return json.loads(trajectories[RESULTS_ATTR_NAME])

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
