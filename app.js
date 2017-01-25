function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, "\\$&");
    var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, " "));
}

function render(album) {
  $.getJSON("/cors?https://itunes.apple.com/search/?term\=" + album + "\&media\=music\&entity\=album\&attributes\=albumTerm\&limit\=1", function(data) {
    var url = data.results[0].artworkUrl100;
    url = url.replace(/100x100/, "1500x1500");
    $(".album-art").attr("src", url)
  });
}

var conf = {
  url: "/notifications",
  debug: true
}

function init() {
    var source = new EventSource(conf.url)

    if (conf.debug) console.log("Binding event source");

    source.addEventListener('trackchange', function(e) {

      if(conf.debug) console.log("e", e);

      // show the new album art work
      render(e.data);
    }, false);
}

init();
