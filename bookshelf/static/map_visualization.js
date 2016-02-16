var map;
var poly;

function initMap() {
	map = new google.maps.Map(document.getElementById('map'), {
		center : {
			lat : 35.300868,
			lng : -120.660782
		},
		zoom : 17,
		mapTypeId : google.maps.MapTypeId.ROAD
	});
	poly = new google.maps.Polyline({
		strokeColor : '#000000',
		strokeOpacity : 1.0,
		strokeWeight : 3
	});
	poly.setMap(map);

	// Add a listener for the click event
	map.addListener('click', addLatLng);
}

//Handles click events on a map, and adds a new point to the Polyline.
function addLatLng(event) {
  var path = poly.getPath();

  // Because path is an MVCArray, we can simply append a new coordinate
  // and it will automatically appear.
  path.push(event.latLng);

  // Add a new marker at the new plotted point on the polyline.
  var marker = new google.maps.Marker({
    position: event.latLng,
    title: '#' + path.getLength(),
    map: map
  });
}

function uploadDrawnPath() {		
	var jsonPath = [];
	
	var arr = poly.getPath().getArray();
	
	for(var i in arr) {
		latlng = {'lat': arr[i].lat()
				, 'lng': arr[i].lng()};
		jsonPath.push(latlng);
	}
		
	$.post("/books/upload_drawn_path", {'path': JSON.stringify(jsonPath)}
	        , function(data, status) {
		alert("Path uploaded: server response data: " + data);
	});
}

function showRawTrajectories() {
	$.get("/books/raw_trajectories", function(data, status) {
		displayPoints("#000000", data);
	});
}

function runSimulatedAnnealing() {
	var epsilon = $("#simulated_annealing_epsilon").val();
	var num_steps = $("#num_steps").val();
	var max_epsilon_jump = $("#max_epsilon_jump").val();

	var url = "/books/simulated_annealing?epsilon=" + epsilon + "&num_steps="
			+ num_steps + "&max_epsilon_jump=" + max_epsilon_jump;

	$.get(url, function(data, status) {
		alert("Ran Simulated Annealing. Server response: "
				+ data['best_epsilon']);
	});
}

function runTraclus() {
	var epsilon = $("#epsilon").val();
	var min_neighbors = $("#min_neighbors").val();
	var min_num_trajectories_in_cluster = $("#min_num_trajectories_in_cluster")
			.val();
	var min_vertical_lines = $("#min_vertical_lines").val();
	var min_prev_dist = $("#min_prev_dist").val();

	var url = "/books/run_traclus?epsilon=" + epsilon + "&min_neighbors="
			+ min_neighbors + "&min_num_trajectories_in_cluster="
			+ min_num_trajectories_in_cluster + "&min_vertical_lines="
			+ min_vertical_lines + "&min_prev_dist=" + min_prev_dist;

	$.get(url, function(data, status) {
		alert("Ran traclus. Server response: " + status);
	});
}

function showFiltered() {
	var url = "/books/filtered";

	$.getJSON(url, function(data, status) {
		displayTrajectories(data['trajectories']);
	});
}

function trueMod(a, b) {
	var temp = a % b;
	return temp < 0 ? temp + b : temp;
}

function hexColorStr(num) {
	var str = num.toString(16);
	if (str.length == 1)
		return '0'.concat(str);
	return str;
}

function showPartitioned() {
	var url = "/books/partitioned";

	$.getJSON(url, function(data) {
		$("partitions").innerHTML = data;
		displayTrajectories(data['trajectories']);
	});
}

function showClusters() {
	var url = "/books/clusters";

	$.getJSON(url, function(data) {
		$("clusters").innerHTML = data;
		displayClusters(data['clusters']);
	});
}

function advanced() {
	var params = $("#advancedParams").val();
	var url = params ? params : "/advanced";

	$.getJSON(url, function(data) {
		$("#locationUpdates").innerHTML = data;
		displayPoints("#000000", data);
	});
}

function colorIterator() {
	var colors = [ 102, 0, 0 ];
	var index = 0;
	var nextIndex = function(index) {
		return (index + 1) % 3;
	};
	var prevIndex = function(index) {
		return trueMod(index - 1, 3);
	};
	var state = false;

	return function() {
		if (state == true) { // decrement previous index
			if (colors[prevIndex(index)] == 0) {
				colors[nextIndex(index)] = colors[nextIndex(index)] + 51;
				state = !state;
			} else {
				colors[prevIndex(index)] = colors[prevIndex(index)] - 51;
			}
		} else { // increment next index
			if (colors[nextIndex(index)] == 102) {
				index = nextIndex(index);
				colors[prevIndex(index)] = colors[prevIndex(index)] - 51;
				state = !state;
			} else {
				colors[nextIndex(index)] = colors[nextIndex(index)] + 51;
			}
		}

		var output = '#';
		for ( var colorIndex in colors) {
			output = output.concat(hexColorStr(colors[colorIndex]));
		}
		return output;
	};
}

function displayTrajectories(trajectories) {
	var colorIter = colorIterator();
	for ( var trajIndex in trajectories) {
		var color = colorIter();
		var displayLine = new google.maps.Polyline({
			path : trajectories[trajIndex],
			strokeColor : color
		});
		displayLine.setMap(map);
	}
}

function displayClusters(clusters) {
	var colorIter = colorIterator()
	for ( var clusterIndex in clusters) {
		var color = colorIter();
		for ( var lineIndex in clusters[clusterIndex]) {
			var displayLine = new google.maps.Polyline({
				path : clusters[clusterIndex][lineIndex],
				strokeColor : color
			});
			displayLine.setMap(map)
		}
	}
}

function displayPoints(color, dataPts) {
	var points = dataPts ? dataPts : JSON.parse(document
			.getElementById("locationUpdates").innerHTML);
	var colorIter = colorIterator();

	for ( var source in points) {
		for ( var lineIndex in points[source]) {
			var drawnLine = new google.maps.Polyline({
				path : points[source][lineIndex],
				strokeColor : (color ? color : colorIter())
			});
			drawnLine.setMap(map);
		}
	}
}
