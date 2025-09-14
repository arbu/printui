'use strict';

var font_families = [];
var preview_throttle = '';

function setStatus(status, message) {
    var style = {
        'success': 'secondary',
        'failure': 'warning',
        'waiting': 'info',
    }[status];
    var icon = {
        'success': 'chevron-circle-right',
        'failure': 'exclamation-circle',
        'waiting': 'hourglass',
    }[status];
    $('#statusBox').attr('class', 'alert alert-' + style);
    $('#statusBox .fas').attr('class', 'pl-0 fas fa-' + icon);
    $('#statusMessage').text(message);
}

function onPrinterResponse(data) {
    if (data.success) {
        setStatus('success', 'Ready.');
    } else if(data.messages) {
        setStatus('failure', data.messages);
    } else {
        setStatus('failure', data.status + ' ' + data.statusText);
    }
    $('#printButton').prop('disabled', false);
}

function formData() {
    return {
        text:           $('#labelText').val(),
        font_index:     $('#fontStyle option:selected').val(),
        font_size:      $('#fontSize').val(),
        label_size:     $('#labelSize option:selected').val(),
        align:          $('input:radio[name=fontAlign]:checked').val(),
        align_vertical: $('input:radio[name=alignVertical]:checked').val(),
        orientation:    $('input:radio[name=orientation]:checked').val(),
        copies:         $('#copies').val(),
        margin_top:     $('#marginTop').val(),
        margin_bottom:  $('#marginBottom').val(),
        margin_left:    $('#marginLeft').val(),
        margin_right:   $('#marginRight').val()
    }
}

function preview() {
    if (preview_throttle) {
        preview_throttle = 'is_running_obsolete';
        return;
    }
    preview_throttle = 'is_running';
    $.ajax({
        type:        'POST',
        url:         '/api/text/preview?return_format=json',
        contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
        data:        formData(),
        success: function(data) {
            if(data.success) {
                $('#previewImg').attr('src', 'data:image/png;base64,' + data.image);
                var img = $('#previewImg')[0];
                img.onload = function() {
                    $('#labelWidth').html( (img.naturalWidth /300*2.54).toFixed(1));
                    $('#labelHeight').html((img.naturalHeight/300*2.54).toFixed(1));
                };
            } else {
                setStatus('failure', data.messages);
            }
        },
        complete: function() {
            if (preview_throttle === 'is_running') {
                preview_throttle = '';
            } else {
                preview_throttle = '';
                preview();
            }
        },
    });
}

function print() {
    $('#printButton').prop('disabled', true);
    setStatus('waiting', 'Processing print request...');
    $.ajax({
        type:     'POST',
        dataType: 'json',
        data:     formData(),
        url:      '/api/text/print',
        success:  onPrinterResponse,
        error:    onPrinterResponse
    });
}


function onStatusResponse(data) {
    if (data.success) {
        $('#modelName').text(data.model);
        if(data.label) {
            for(option of $('#labelSize option').get()) {
                if(option.value == data.label){
                    $('#labelName').text(option.text);
                    break;
                }
            }
        } else {
            $('#labelName').text("none");
        }
    } else {
        $('#modelName').text("not available");
        $('#labelName').text("not available");
    }
    onPrinterResponse(data);
}

function updatePrinterStatus() {
    $('#printButton').prop('disabled', true);
    setStatus('waiting', 'Requesting printer status...');
    $.ajax({
        type:     'GET',
        url:      '/api/status',
        success:  onStatusResponse,
        error:    onStatusResponse
    });
}

function updateFontStyles() {
    var old_style = $('#fontStyle option:selected').text() || "Regular";
    $('#fontStyle').find('option').remove();
    $.each(font_families[$('#fontFamily option:selected').text()], function(i, info) {
        $('#fontStyle').append($('<option>', {
            text:     info[2],
            value:    info[0],
        }));
        if(info[2] == old_style) {
            $('#fontStyle').val(info[0]);
            old_style = "";
        }
    });
    if(old_style) {
        $('#fontStyle option[text="Regular"]').attr("selected", "selected");
    }
    preview();
}

$.ajax({
    type:     'GET',
    url:      '/api/config',
    error:    function(error) {
        alert("Failed to load config: " + error.status + " " + error.statusText);
    },
    success:  function(data) {
        if(!data.success) {
            alert("Failed to load config: " + data.messages);
            return;
        }
        $.each(data.label_sizes, function(i, size) {
            var identifier = size[0],
                name = size[1];
            $('#labelSize').append($('<option>', {
                value: identifier,
                text: name,
            }));
        });

        $.each(data.fonts, function(i, font) {
            var index = font[0],
                family = font[1];
            if(!font_families[family]) {
                font_families[family] = [];
                $('#fontFamily').append($('<option>', {
                    text: family,
                }));
            }
            font_families[family].push(font);
            if(index == data.default_values.font_index) {
                $('#fontFamily option:contains("' + family + '")').attr("selected", "selected");
            }
        });

        updateFontStyles();

        $('input:radio[name=orientation]').val([data.default_values.orientation]);
        $('#fontStyle').val(data.default_values.font_index);
        $('#fontSize').val(data.default_values.font_size);
        $('input:radio[name=fontAlign]').val([data.default_values.align]);
        $('input:radio[name=alignVertical]').val([data.default_values.align_vertical]);
        $('#marginTop').val(data.default_values.margin_top);
        $('#marginLeft').val(data.default_values.margin_left);
        $('#marginRight').val(data.default_values.margin_right);
        $('#marginBottom').val(data.default_values.margin_bottom);
        $('#labelText').val(data.default_values.text);
        $('#copies').val(data.default_values.copies);

        updatePrinterStatus();

        preview();
    }
});
