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

import logging

from bookshelf import get_model, storage
from flask import current_app
from gcloud import pubsub
import psq
import requests
import model_datastore
from traclus_impl.geometry import LineSegment
from traclus_impl.geometry import Point
from bookshelf.model_datastore import store_partitioned_trajectories
from traclus_impl.coordination import the_whole_enchilada
import math
from traclus_impl.parameter_estimation import TraclusSimulatedAnnealingState
from traclus_impl.parameter_estimation import TraclusSimulatedAnnealer
from traclus_impl.processed_trajectory_connecting import \
get_find_other_nearby_neighbors_func, FilteredTrajectory,\
    compute_graph_component_ids, find_shortest_connection

from traclus_impl.processed_trajectory_connecting import \
build_point_graph

COORDINATE_SCALER = 1.0


# [START get_books_queue]
def get_books_queue():
    client = pubsub.Client(
        project=current_app.config['PROJECT_ID'])

    # Create a queue specifically for processing books and pass in the
    # Flask application context. This ensures that tasks will have access
    # to any extensions / configuration specified to the app, such as
    # models.
    return psq.Queue(
        client, 'books', extra_context=current_app.app_context)
    
def get_trajectory_filter_queue():
    client = pubsub.Client(
        project=current_app.config['PROJECT_ID'])
    
    return psq.Queue(
        client, 'trajectory_filter', extra_context=current_app.app_context)
# [END get_books_queue]

def construct_graph_from_processed_trajectories(filtered_trajectories, \
                                                max_distance_between_connected_different_trajs):
    other_neighbors_func = \
    get_find_other_nearby_neighbors_func(max_distance_between_connected_different_trajs)
    
    cur_index = 0
    graph_input = []
    for traj in filtered_trajectories:
        point_traj = map(lambda x: Point(x['lat'], x['lng']), traj)
        graph_input.append(FilteredTrajectory(point_traj, cur_index))
        cur_index += 1
    
    def dummy_find_other_neighbors_func(pt_node, pt_graph):
        return []
    pt_graph = build_point_graph(graph_input, other_neighbors_func)
    compute_graph_component_ids(pt_graph=pt_graph, \
                                find_other_neighbors_func=dummy_find_other_neighbors_func)
    return pt_graph

def compute_shortest_path_between_points(pt_graph, start_pt, end_pt, \
                                         max_dist_to_existing_pt):
    shortest_path, shortest_distance = find_shortest_connection(start_pt=start_pt, \
                                    end_pt=end_pt, \
                                    pt_graph=pt_graph, \
                                    max_dist_to_existing_pt=max_dist_to_existing_pt)
    if shortest_path == None and shortest_distance == None:
        return None, None
    
    return map(lambda pt: {'lat': pt.x, 'lng': pt.y}, shortest_path), shortest_distance

def filter_trajectories():
    print "Entered function to filter trajectories: BEEF"
    unfiltered = model_datastore.get_all_location_updates()
    filtered_trajectories = \
    model_datastore.filter_trajectories(trajectories=unfiltered)
    model_datastore.store_filtered_trajectories(filtered_trajectories=filtered_trajectories)
    return

def run_simulated_annealing_for_epsilon(initial_epsilon, num_steps, max_epsilon_jump):
    all_raw_point_lists = get_normalized_datastore_trajectories()
    initial_state = TraclusSimulatedAnnealingState(input_trajectories=all_raw_point_lists, \
                                                epsilon=initial_epsilon)
    traclus_sim_anneal = TraclusSimulatedAnnealer(initial_state=initial_state, \
                                                      max_epsilon_step_change=max_epsilon_jump)
    traclus_sim_anneal.updates = max(10, num_steps)
    traclus_sim_anneal.steps = num_steps
    best_state, best_energy = traclus_sim_anneal.anneal()
    return best_state.get_epsilon()

def create_line_seg(start, end):
    return LineSegment.from_tuples(start, end)

def remove_successive_points_at_same_spots(point_list):
    p_iter = iter(point_list)
    prev = p_iter.next()
    out = [prev]
    
    for p in p_iter:
        if prev.x == p.x and prev.y == p.y:
            print "removing same point in sequential spot"
        else:
            out.append(p)
    return out

def remove_points_too_close(point_list):
    p_iter = iter(point_list)
    prev = p_iter.next()
    out = [prev]
    
    for p in p_iter:
        if prev.distance_to(p) > 0.0:
            out.append(p)
            prev = p
            
    return out
            
def get_normalized_datastore_trajectories():
    raw_trajectories = model_datastore.get_all_location_updates()
        
    print "HERE ARE THE RAW TRAJECTORIES: \n" + str(raw_trajectories)
        
    def dict_list_to_point_list(dict_list):
        return map(lambda x: Point(x['lat'], x['lng']), dict_list)
    
    normal_traj_lists = model_datastore.get_raw_trajectories()
        
    print "\n\nHERE ARE THE NORMALIZED FORMAT TRAJECTORIES: \n" + str(normal_traj_lists)
    print "\n LENGTH OF NORMAL TRAJ LIST IS " + str(len(normal_traj_lists))
    
    all_raw_point_lists = []
    for dict_list in normal_traj_lists:
        print "here is what we're trying to go from dict list to point list on: " \
         + str(dict_list)
        point_list = dict_list_to_point_list(dict_list)
        if len(point_list) < 2:
            continue
        traj_list = remove_successive_points_at_same_spots(point_list)
        if len(traj_list) >= 2:
            all_raw_point_lists.append(traj_list)
        
    if len(all_raw_point_lists) <= 1:
        raise ValueError("length of all raw point lists is " + \
                         str(len(all_raw_point_lists)))
        
    def get_min_dist():
        min_dist = 1000
        for traj in all_raw_point_lists:
            p_iter = iter(traj)
            prev = p_iter.next()
            for p in p_iter:
                min_dist = min(min_dist, prev.distance_to(p))
        return min_dist
            
    print "min dist is " + str(get_min_dist())
        
    def get_scaled_trajs(traj_list, scale):
        def scale_coordinates(point_list):
            return map(lambda p: Point(p.x * scale, p.y * scale), point_list)
        return map(scale_coordinates, traj_list)
        
    all_raw_point_lists = get_scaled_trajs(all_raw_point_lists, COORDINATE_SCALER)
    all_raw_point_lists = map(remove_points_too_close, all_raw_point_lists)
    all_raw_point_lists = filter(lambda x: len(x) >= 2, all_raw_point_lists)
    
    return all_raw_point_lists


def run_the_whole_enchilada(epsilon, min_neighbors, min_num_trajectories_in_cluster, \
                            min_vertical_lines, min_prev_dist): 
    all_raw_point_lists = get_normalized_datastore_trajectories()   
    print "HERE ARE THE POINT LISTS WERE PASSING IN TO TRACLUS: " + str(all_raw_point_lists)
        
    print "ABOUT to run the whole enchilada with a min neighbors of " + str(min_neighbors)
    result_trajectories = the_whole_enchilada(point_iterable_list=all_raw_point_lists, \
                        epsilon=epsilon, \
                        min_neighbors=min_neighbors, \
                        min_num_trajectories_in_cluster=min_num_trajectories_in_cluster, \
                        min_vertical_lines=min_vertical_lines, \
                        min_prev_dist=min_prev_dist, \
                        partitioned_points_hook=model_datastore.store_partitioned_trajectories, \
                        clusters_hook=model_datastore.store_clusters)
    
    if len(result_trajectories) == 0:
        raise ValueError("length of resulting trajectories is " + str(len(result_trajectories)))
    
    model_datastore.store_filtered_trajectories(filtered_trajectories=result_trajectories)
        
# [START process_book]
def process_book(book_id):
    """
    Handles an individual Bookshelf message by looking it up in the
    model, querying the Google Books API, and updating the book in the model
    with the info found in the Books API.
    """

    model = get_model()

    book = model.read(book_id)

    if not book:
        logging.warn("Could not find book with id {}".format(book_id))
        return

    if 'title' not in book:
        logging.warn("Can't process book id {} without a title."
                     .format(book_id))
        return

    logging.info("Looking up book with title {}".format(book[
                                                        'title']))

    new_book_data = query_books_api(book['title'])

    if not new_book_data:
        book['something'] = "book not found in api"
        model.update(book, book_id)
        return

    book['title'] = new_book_data.get('title')
    book['author'] = ', '.join(new_book_data.get('authors', []))
    book['publishedDate'] = new_book_data.get('publishedDate')
    book['description'] = new_book_data.get('description') + "________added_this"
    book['something'] = "book api found this one"


    # If the new book data has thumbnail images and there isn't currently a
    # thumbnail for the book, then copy the image to cloud storage and update
    # the book data.
    if not book.get('imageUrl') and 'imageLinks' in new_book_data:
        new_img_src = new_book_data['imageLinks']['smallThumbnail']
        book['imageUrl'] = download_and_upload_image(
            new_img_src,
            "{}.jpg".format(book['title']))

    model.update(book, book_id)
# [END process_book]


# [START query_books_api]
def query_books_api(title):
    """
    Queries the Google Books API to find detailed information about the book
    with the given title.
    """
    r = requests.get('https://www.googleapis.com/books/v1/volumes', params={
        'q': title
    })

    try:
        data = r.json()['items'][0]['volumeInfo']
        return data

    except KeyError:
        logging.info("No book found for title {}".format(title))
        return None

    except ValueError:
        logging.info("Unexpected response from books API: {}".format(r))
        return None
# [END queue_books_api]


def download_and_upload_image(src, dst_filename):
    """
    Downloads an image file and then uploads it to Google Cloud Storage,
    essentially re-hosting the image in GCS. Returns the public URL of the
    image in GCS
    """
    r = requests.get(src)

    if not r.status_code == 200:
        return

    return storage.upload_file(
        r.content,
        dst_filename,
        r.headers.get('content-type', 'image/jpeg'))
