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
from polypaths_planar_override import LineSegment
from polypaths_planar_override import Point
from bookshelf.model_datastore import store_partitioned_trajectories


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

def filter_trajectories():
    print "Entered function to filter trajectories: BEEF"
    unfiltered = model_datastore.get_all_location_updates()
    filtered_trajectories = \
    model_datastore.filter_trajectories(trajectories=unfiltered)
    model_datastore.store_filtered_trajectories(filtered_trajectories=filtered_trajectories)
    return

def create_line_seg(start, end):
    return LineSegment.from_points([Point(start[0], start[1]), Point(end[0], end[1])])

def upload_partitioned_trajectories():
    trajs = [create_line_seg((35.3015897, -120.6630498), \
                             (35.3009616, -120.6625416)), \
                             create_line_seg((35.3002847, -120.6608752), \
                                             (35.2998518, -120.6604413))]
    model_datastore.store_partitioned_trajectories(trajs)
    
def upload_clusters():
    class MockTrajSeg:
        def __init__(self, line_seg):
            self.line_segment = line_seg
    class MockCluster:
        def __init__(self, point_list):
            self.segs = point_list
        def get_trajectory_line_segments(self):
            return self.segs
        
    segs_a = [create_line_seg((35.3015897, -120.6630498), \
                             (35.3009616, -120.6625416)), \
                             create_line_seg((35.3002847, -120.6608752), \
                                             (35.2998518, -120.6604413))]
    traj_segs = map(lambda x: MockTrajSeg(x), segs_a)
    model_datastore.store_clusters([MockCluster(traj_segs)])
        

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
