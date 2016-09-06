$(function(){
  $(".track").text(getParameterByName("song"));
  $(".album").text(getParameterByName("album"));
  $(".artist").text(getParameterByName("artist"));
  $.getJSON("https://crossorigin.me/https://itunes.apple.com/search/?term\="+getParameterByName("album")+"\&media\=music\&entity\=album\&attributes\=albumTerm\&limit\=1", function(data) {
    var url = data.results[0].artworkUrl100;
    url = url.replace(/100x100/, "1500x1500");
    $(".album-art").attr("src", url)
  })
})
function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, "\\$&");
    var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, " "));
}
