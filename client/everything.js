var receiptTemplate = Handlebars.compile($("#receipt").html());
var streams, formState;

$(function() {
	/*
	function toggle() {
		$(".current").removeClass();
		$(formState.stream[formState.currentPage]).addClass('current');
		$(window).scrollTop($(".current").offset().top);
		$("#prev, #next").show();
		
		if (formState.currentPage == 0) {
			$("#prev").hide();
		}
		
		if (formState.currentPage == formState.stream.length -1) {
			$("#next").hide();
		}
	}
	*/

	streams = {
		"update": $("form[name=why_are_you_here], form[name=details_of_applicant], form[name=submission]"),
		"new": $("form")
	};
	
	formState = {
		stream: streams['new']
	};

	$("input[name=purpose]").click(function() {
		$("form").removeClass("current");
		formState.stream = streams[$(this).val()];
		formState.stream.addClass("current");
	});

	/*
	$("#next").click(function() {
		formState.currentPage = Math.min(formState.currentPage + 1, formState.stream.length - 1);
		toggle();
	});
	
	$("#prev").click(function() {
		formState.currentPage = Math.max(formState.currentPage - 1, 0);
		toggle();
	});
	*/

	if (location.hash == "#new") {
		$("#new").click();
	} else if (location.hash == "#update") {
		$("#update").click();
	}
});

var RecaptchaOptions = {theme: 'clean'};
$("#recaptcha_response_field").live("keypress", function(e) { 
	if((e.which || e.keyCode) == 13) { 
		e.preventDefault();
	} 
});

function generateReceipt(obj) {
	$("#signup").children().not('header').remove();
	$("#signup").append($("<form><h2>Thank you!</h2></form>"));
	$("#signup").append($("<article><p>Your membership application will be processed in the next 72 hours. You will receive a notification by email when this process is complete. Thank for your applying for membership with Pirate Party Australia.</p><p>If you have any questions or do not receive notification within 72 hours, please email us at <a href='mailto:enquiries@pirateparty.org.au'>enquiries@pirateparty.org.au</a>.</p><p style='text-align: center'><a href='http://pirateparty.org.au'>Return to Homepage</a></p></article>"));
	var div = $("<div style='text-align: center'></div>");
	var button = $("<button type='button'>Print Receipt</button>");
	button.click(function() { window.print(); });
	div.append(button);
	$("#signup").append(receiptTemplate(obj));
	$("#signup").append(div);
	window.scrollTo(0);
}

function submit(isTest) {
	var forms = formState.stream, form, res,
		i, ii, valid = true, obj, first;

	for (i = 0, ii = forms.length; i < ii; ++i) {
		if (!validate(forms[i])) {
			valid = false;
		}
	}
	
	if (!valid) {
		$('.invalid').first().focus();
		alert("Validation failed. Please check for invalid or incomplete fields and try again.");
	}

	if (valid) {
		obj = {};
		obj['version'] = $('[name=version]').val();
		forms.each(function() {
			obj[this.getAttribute('name')] = getFormData(this);
		});
		obj['submission']['date'] = new Date().toISOString();

		if (isTest) {
			console.log(obj);
		} else {
			var self = this;
			$(this).attr("disabled", "disabled");
			$(this).text("Submitting...");
			$.ajax("/app/new_member", {
				type: "POST",
				data: {
					form: JSON.stringify(obj)
				}, 
				success: function(data) {
					if (data == "invalid captcha") {
						alert("Invalid captcha. Please try again.");
						$(self).removeAttr("disabled");
						$(self).text("Submit");
						return;
					}
					
					if (data == "bot detected") {
						alert("Go away, bot.");
						return;
					}

					if (typeof data === "string") {
						alert("Unhandled error: " + data);
						return;
					}

					generateReceipt(data);
				}, 
				error: function(data) {
					alert("An unknown error occurred.");
					$(self).removeAttr("disabled");
					$(self).text("Submit");
				}
			});
		}
		
	}
}

function validate(form) {
	var res = $(form).find("[required]"),
		i, ii, node;
	
	$(form).find(".invalid").removeClass("invalid");
	for (i = 0, ii = res.length; i < ii; ++i) {
		node = $(res[i]);
		if (node.hasClass('date') && !/^(0?[1-9]|[12][0-9]|3[01])\/(0?[1-9]|1[012])\/(19|20)\d\d$/.test(node.val())) {
			node.addClass('invalid');
			node.siblings('.invalid-msg').addClass('invalid');	
		} else if ((node.attr('type') == "checkbox") ? !node[0].checked : node.val() == "") {
			if (node.hasClass('output')) {
				node.parent().find('canvas').addClass('invalid');
				node.parent().parent().find('.invalid-msg').addClass('invalid');	
			} else {
				node.addClass('invalid');
				node.parent().find('.invalid-msg').addClass('invalid');	
			}
		}
	}
	return $(form).find(".invalid").length == 0;
}

function getFormData(form) {
	var obj = {}, i, ii, j, jj, parents, current,
		inputs = $(form)[0].elements, input;
	
	for (i = 0, ii = inputs.length; i < ii; ++i) {
		if (inputs[i].tagName.toLowerCase() == "section") {
			continue;
		}
		
		input = $(inputs[i]);
		if (input.attr('name') == null || input.attr('name') == "") {
			continue;
		}
		parents = input.parents('section').toArray().reverse();
		current = obj;
		
		for (j = 0, jj = parents.length; j < jj; ++j) {
			if (current[parents[j].getAttribute('name')] == null) {
				current[parents[j].getAttribute('name')] = {};
			}
			current = current[parents[j].getAttribute('name')];
		}
		
		if (input[0].getAttribute('type') == "checkbox") {
			current[input[0].getAttribute('name')] = input[0].checked;
		} else if (input[0].getAttribute('type') == "radio") {
			current[input[0].getAttribute('name')] = $("[name=" + input.attr('name') + "]:checked").val();
		} else if (input.hasClass('output')) {
			current['signature'] = input.parent().find('canvas')[0].toDataURL();
		} else {
			current[input[0].getAttribute('name')] = input.val();
		}
	}

	return obj;
}

$(document).ready(function() {	
	$("button").click(function(e) {
		e.preventDefault();
	});
	$("button").submit(function(e) {
		e.preventDefault();
	});

	$("#submit").click(function() {
		submit.call(this, false);
	});
	
	$("#signature").signaturePad({
		drawOnly: true
	});

	$("input[required], select[required]").change(function() {
		validate(this.parentNode);
	});
	
	$("[id*=show\\:]").change(function() {
		var id = $(this).attr('id').split(":")[1];
		if (this.checked) {
			$("#" + id).attr('style', '');
		} else {
			$("#" + id).attr('style', 'display: none');
		}
	});
});