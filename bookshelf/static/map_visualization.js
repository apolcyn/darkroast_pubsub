var map;

function initMap() {
	map = new google.maps.Map(document.getElementById('map'), {
		center : {
			lat : 35.300868,
			lng : -120.660782
		},
		zoom : 17,
		mapTypeId : google.maps.MapTypeId.ROAD
	});
	displayPoints();
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
		displayPartitionedTrajectories(data['trajectories']);
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

function displayClusters(clusters) {
	var colorIter = colorIterator()
	for ( var clusterIndex in clusters) {
		color = colorIter()
		for ( var lineIndex in clusters[clusterIndex]) {
			var displayLine = new google.maps.Polyline({
				path : clusters[clusterIndex][lineIndex],
				strokeColor : color
			})
			displayLine.setMap(map)
		}
	}
}

function displayPartitionedTrajectories(trajectories) {
	for ( var index in trajectories) {
		var displayLine = new google.maps.Polyline({
			path : trajectories[index]
		})
		displayLine.setMap(map)
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
