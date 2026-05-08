// npm i simplepush-notifications
const simplepush = require('simplepush-notifications');

// Send notification
simplepush.send({key: 'HuxgBB', title: 'title', message: 'message', event: 'event'});

// Send encrypted notification
simplepush.send({key: 'HuxgBB', title: 'title', message: 'message', event: 'event', password: 'password', salt: 'salt'});

// Check for errors
var callback = function (error) {
	console.log(error);
}
simplepush.send({key: 'HuxgBB', title: 'title', message: 'message', event: 'event'}, callback);
