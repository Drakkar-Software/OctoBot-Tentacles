// move content to draggable

$("#move-strategy-settings").click(function() {
    $("#strategy-settings").appendTo($("#strategy-modal-content"));
    // hide tab and remove active
    $("#strategy-settings-tab").removeClass("active")
    $("#strategy-settings-tab").addClass("d-none")
    // todo click first visible tab after editor - works but its tab button is not active
    $("#backtesting-tab").trigger('click');

});

// move content back to tab
$("#move-strategy-settings-back").click(function() {
    $("#strategy-settings").appendTo($("#toolbox-tabcontent"));
    $("#strategy-settings-tab").removeClass("active")
    $("#strategy-settings-tab").removeClass("d-none")
});


// modal draggable

$('#move-strategy-settings').click(function() {


  //open modal
  $('#dragable_modal').modal({
    backdrop: false,
    show: true
  });
  // todo reset modal if it isn't visible doesnt work
  if (!($('.modal.in').length)) {
    $('.modal-dialog').css({
      top: 20,
      left: 100
    });
  }

  $('.modal-dialog').draggable({
    cursor:"move",
    handle: ".dragable_touch"
  });
});
