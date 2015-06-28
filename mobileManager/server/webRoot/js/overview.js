// set global configuration variables
var request = new XMLHttpRequest();


// processes the response of the server for the
// requested data
function processResponse() {
	
	if (request.readyState == 4) {

		// remove old nodes output
		// and generate a new clear one
		var nodeTableObj = document.getElementById("contentTable");
		var newBody = document.createElement("tbody");
		var newTr = document.createElement("tr");
		var newTd = document.createElement("td");
		var newB = document.createElement("b");
		newB.textContent = "Nodes:";
		newTd.appendChild(newB);
		newTr.appendChild(newTd);
		newBody.appendChild(newTr);
		var oldBody = document.getElementById("contentTableBody");
		oldBody.removeAttribute("id");
		newBody.setAttribute("id", "contentTableBody");
		nodeTableObj.replaceChild(newBody, oldBody);
		delete oldBody;

		// get JSON response and parse it
		var response = request.responseText;
		var alertSystemInformation = JSON.parse(response);
		var internals = alertSystemInformation["internals"];
		var options = alertSystemInformation["options"];
		var nodes = alertSystemInformation["nodes"];
		var sensors = alertSystemInformation["sensors"];
		var managers = alertSystemInformation["managers"];
		var alerts = alertSystemInformation["alerts"];
		var alertLevels = alertSystemInformation["alertLevels"];

		// get server time
		var serverTime = 0.0;
		for(i = 0; i < internals.length; i++) {
			if(internals[i]["type"].toUpperCase() == "SERVERTIME") {
				var serverTime = internals[i]["value"]
			}
		}


		var boxDiv = document.createElement("div");
		boxDiv.className = "box";

		var sensorTable = document.createElement("table");
		sensorTable.style.width = "100%";
		sensorTable.setAttribute("border", "0");
		boxDiv.appendChild(sensorTable);


		// add all sensors to the output
		for(i = 0; i < sensors.length; i++) {

			var sensorId = sensors[i]["id"];
			var nodeId = sensors[i]["nodeId"];
			var description = sensors[i]["description"];
			var lastStateUpdated = sensors[i]["lastStateUpdated"];
			var state = sensors[i]["state"];
			var connected = 0;


			// get connected information from corresponding node
			for(j = 0; j < nodes.length; j++) {
				if(nodes[j]["id"] == nodeId) {
					var connected = nodes[j]["connected"];
				}
			}


			// output sensor descriptions according to state/connected/updated
			var newTr = document.createElement("tr");
			var newTd = document.createElement("td");
			newTd.textContent = description;
			if(state == 0) {
				newTd.className = "okTd";
			}
			else {
				newTd.className = "triggeredTd";
			}
			if(lastStateUpdated < (serverTime - 2* 60)) {
				newTd.className = "failTd";
			}
			if(connected == 0) {
				newTd.className = "failTd";
			}
			newTr.appendChild(newTd);
			sensorTable.appendChild(newTr);


		}


		// add node to the node table
		var nodeTableObj =
			document.getElementById("contentTableBody");
		var newTr = document.createElement("tr");
		var newTd = document.createElement("td");
		newTd.appendChild(boxDiv);
		newTr.appendChild(newTd);
		nodeTableObj.appendChild(newTr);

	}
}


// requests the data of the alert system
function requestData() {
	var url = "./getJson.php";
	request.open("GET", url, true);
	request.onreadystatechange = processResponse;
	request.send(null);

	// wait 10 seconds before requesting the next data update
	window.setTimeout("requestData()", 10000);	
}

requestData();