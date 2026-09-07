.pragma library

function duration(seconds) {
    if (!seconds || seconds <= 0) {
        return ""
    }
    var total = Math.floor(seconds)
    var h = Math.floor(total / 3600)
    var m = Math.floor((total % 3600) / 60)
    var s = total % 60

    function pad(n) { return n < 10 ? "0" + n : "" + n }

    return h > 0 ? h + ":" + pad(m) + ":" + pad(s)
                 : m + ":" + pad(s)
}

function count(n) {
    if (!n || n <= 0) {
        return ""
    }
    if (n >= 1000000) {
        return (n / 1000000).toFixed(n < 10000000 ? 1 : 0) + "M"
    }
    if (n >= 1000) {
        return (n / 1000).toFixed(n < 10000 ? 1 : 0) + "K"
    }
    return "" + n
}
