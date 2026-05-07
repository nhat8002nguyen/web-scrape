const querystring = require('querystring');
const request = require('request');

const url = 'https://api.simplepush.io/send';
let data = { 'key': 'HuxgBB', 'title': 'title', 'msg': 'message', 'event': 'event' };

request.post({
  url: url,
  body: querystring.stringify(data),
}, function(error, response, body){
  console.log(body);
});