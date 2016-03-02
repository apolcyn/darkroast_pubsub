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

from bookshelf import get_model, oauth2, storage, tasks, model_datastore
from flask import Blueprint, current_app, redirect, render_template, request, \
    session, url_for, jsonify
import json
from polypaths_planar_override import Point


crud = Blueprint('crud', __name__)


def upload_image_file(file):
    """
    Upload the user-uploaded file to Google Cloud Storage and retrieve its
    publicly-accessible URL.
    """
    if not file:
        return None

    public_url = storage.upload_file(
        file.read(),
        file.filename,
        file.content_type
    )

    current_app.logger.info(
        "Uploaded file %s as %s.", file.filename, public_url)

    return public_url


@crud.route("/")
def list():
    token = request.args.get('page_token', None)
    books, next_page_token = get_model().list(cursor=token)

    return render_template(
        "list.html",
        books=books,
        next_page_token=next_page_token)
    
@crud.route("/seemap")
def show_map():
    return render_template("seemap.html")

@crud.route("/get_directions")
def get_directions():
    start_lat = float(request.args.get("start_lat"))
    start_lng = float(request.args.get("start_lng"))
    end_lat = float(request.args.get("end_lat"))
    end_lng = float(request.args.get("end_lng"))
    
    start_pt = json.dumps({'lat': start_lat, 'lng': start_lng})
    end_pt = json.dumps({'lat': end_lat, 'lng': end_lng})
    query_str = "?start_pt=" + start_pt + \
    "&end_pt=" + end_pt + \
    "&max_inter_traj_distance=" + str(0.001) + \
    "&max_dist_to_existing_pt=" + str(0.0001)
    
    return redirect("/books/build_graph_and_find_path" + query_str)

@crud.route("/migrate_locations")
def migrate_locations():
    all_locations = model_datastore.get_all_location_updates()
    for update_list in all_locations.values():
        traj = update_list[0]
        if len(traj) > 1:
            model_datastore.store_new_trajectory_update(new_trajectory=traj, \
                                                        drawn_by_hand=False)
    return "Stored em"

@crud.route("/upload_drawn_path", methods=['POST'])
def upload_drawn_path():
    def validate(coord):
        if coord['lat'] == None or coord['lng'] == None:
            raise ValueError
        return coord
    
    path = map(validate, json.loads(request.values.get('path')))  
    
    model_datastore.store_new_trajectory_update(new_trajectory=path, \
                                                drawn_by_hand=True)
    return "just uploaded new trajectory"

@crud.route("/raw_trajectories")
def get_raw_trajectories():
    raw_traj = model_datastore.get_raw_trajectories()
    return jsonify({'trajectories': raw_traj})

@crud.route("/locations")
def get_location_updates():
    unfiltered = model_datastore.get_all_location_updates()
    #tasks.upload_clusters()
    #tasks.upload_partitioned_trajectories()
    #task_queue = tasks.get_trajectory_filter_queue()
    #task_queue.enqueue(tasks.filter_trajectories)
    print "Just enqueued a task to filter trajectories BEEF."
    return jsonify(unfiltered)

@crud.route("/simulated_annealing")
def simulated_annealing_for_epsilon():
    epsilon = float(request.args.get('epsilon'))
    num_steps = int(request.args.get('num_steps'))
    max_epsilon_jump = float(request.args.get('max_epsilon_jump'))
    
    best_epsilon = tasks.run_simulated_annealing_for_epsilon(initial_epsilon=epsilon, \
                                              num_steps=num_steps, \
                                              max_epsilon_jump=max_epsilon_jump)
    return jsonify({"best_epsilon": best_epsilon})

@crud.route("/run_traclus")
def run_traclus():
    epsilon = float(request.args.get('epsilon'))
    min_neighbors = int(request.args.get('min_neighbors'))
    min_num_trajectories_in_cluster = int(request.args.get('min_num_trajectories_in_cluster'))
    min_vertical_lines = int(request.args.get('min_vertical_lines'))
    min_prev_dist = float(request.args.get('min_prev_dist'))
    
    tasks.run_the_whole_enchilada(epsilon=epsilon, \
                                  min_neighbors=min_neighbors, \
                                  min_num_trajectories_in_cluster=min_num_trajectories_in_cluster, \
                                  min_vertical_lines=min_vertical_lines, \
                                  min_prev_dist=min_prev_dist)
    return "Just ran traclus"

@crud.route("/filtered")
def get_filtered_trajectories():
    filtered = model_datastore.get_filtered_trajectories()
    return jsonify({'trajectories':filtered})

@crud.route("/partitioned")
def show_partitioned_trajectories():
    traj = model_datastore.get_partitioned_trajectories()
    return jsonify({'trajectories': traj})

@crud.route("/clusters")
def show_clusters():
    clusters = model_datastore.get_clusters()
    return jsonify({'clusters': clusters})

@crud.route("/mine")
@oauth2.required
def list_mine():
    token = request.args.get('page_token', None)

    books, next_page_token = get_model().list_by_user(
        user_id=session['profile']['id'],
        cursor=token)

    return render_template(
        "list.html",
        books=books,
        next_page_token=next_page_token)
    
@crud.route("/build_graph_and_find_path")
def build_graph_and_find_path():
    start_pt_dict = json.loads(request.args.get('start_pt'))
    end_pt_dict = json.loads(request.args.get('end_pt'))
    max_inter_traj_distance = float(request.args.get('max_inter_traj_distance'))
    max_dist_to_existing_pt = float(request.args.get('max_dist_to_existing_pt'))
    
    start_pt = Point(start_pt_dict['lat'], start_pt_dict['lng'])
    end_pt = Point(end_pt_dict['lat'], end_pt_dict['lng'])
    
    filtered_trajectories = model_datastore.get_filtered_trajectories()
    pt_graph = tasks.construct_graph_from_processed_trajectories(filtered_trajectories, \
                                                                 max_inter_traj_distance)
    shortest_path, shortest_dist = tasks.compute_shortest_path_between_points(pt_graph=pt_graph, \
                                                               start_pt=start_pt, \
                                                               end_pt=end_pt, \
                                                               max_dist_to_existing_pt=max_dist_to_existing_pt)
    if shortest_path == None:
        return jsonify({'path_found': False})
    else:
        return jsonify({'path_found': True, 'shortest_path': shortest_path})

@crud.route('/<id>')
def view(id):
    book = get_model().read(id)
    return render_template("view.html", book=book)


@crud.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        data = request.form.to_dict(flat=True)

        # If an image was uploaded, update the data to point to the new image.
        image_url = upload_image_file(request.files.get('image'))

        if image_url:
            data['imageUrl'] = image_url

        # If the user is logged in, associate their profile with the new book.
        if 'profile' in session:
            data['createdBy'] = session['profile']['displayName']
            data['createdById'] = session['profile']['id']

        book = get_model().create(data)

        # [START enqueue]
        q = tasks.get_books_queue()
        q.enqueue(tasks.process_book, book['id'])
        # [END enqueue]

        return redirect(url_for('.view', id=book['id']))

    return render_template("form.html", action="Add", book={})


@crud.route('/<id>/edit', methods=['GET', 'POST'])
def edit(id):
    book = get_model().read(id)

    if request.method == 'POST':
        data = request.form.to_dict(flat=True)

        image_url = upload_image_file(request.files.get('image'))

        if image_url:
            data['imageUrl'] = image_url

        book = get_model().update(data, id)

        q = tasks.get_books_queue()
        q.enqueue(tasks.process_book, book['id'])

        return redirect(url_for('.view', id=book['id']))

    return render_template("form.html", action="Edit", book=book)


@crud.route('/<id>/delete')
def delete(id):
    get_model().delete(id)
    return redirect(url_for('.list'))
