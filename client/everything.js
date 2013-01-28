var receiptTemplate = Handlebars.compile($("#receipt").html());
var streams, formState;

function mangleFormForAdminUpdate() {
    var why = $("form[name=why_are_you_here]");
    why.empty().append($("<input type='hidden' name='purpose' value='admin-update'>"))
    why.hide();
    var x = $("<form name='auth'>");
    x.attr('name', 'auth');
    x.append($("<h2>Authentication</h2>"));
    var article = $("<article></article>");
    x.append(article);
    article.append($("<input placeholder='username' name='username'><br><input placeholder='password' name='password' type='password'>"));
    var button = $("<button>Prefill</button>");
    button.click(function() {
        prefill();
    });
    article.append(button);
    article.append($("<br><textarea style='width: 99%' name='comment' placeholder='Enter reason for update here.'></textarea><br>"));
    x.insertAfter(why);

	var path = location.pathname.substr(1).split('/');
    var uuid = path[path.indexOf("update")+1];
    if (uuid != null) {
		window.memberUuid = uuid;
	}
    
    var submit = $("#submit-block").remove();
    var botkill = $("#botkill").remove()
    $("form[name=submission]").attr('id', '').empty().append(botkill).append(submit);
}

function prefill() {
    function doit(data, node) {
        for (var prop in data) {
            if (typeof data[prop] == "string") {
                node.find("[name="+prop+"]").val(data[prop]);
            } else if (typeof data[prop] == "object" && data[prop] != null) {
                doit(data[prop], node.find("[name="+prop+"]"));
            }
        }
    }
    
    $.post("/member_prefill", {
        username: $("[name=username]").val(),
        password: $("[name=password]").val(),
        uuid: window.memberUuid
    }, function(data) {
        if (typeof data == "string") {
            alert(data);
            return;
        }

       doit(data, $("body"))

    });
}

$(function() {
	streams = {
		"update": "form[name=why_are_you_here], form[name=details_of_applicant], form[name=submission]",
		"admin-update": "form[name=why_are_you_here], form[name=auth], form[name=details_of_applicant], form[name=submission]",
		"new": "form"
	};
	
	formState = {
		stream: $(streams['new'])
	};

	$("input[name=purpose]").click(function() {
		$("form").removeClass("current");
		formState.stream = $(streams[$(this).val()]);
		formState.stream.addClass("current");
	});

	var path = location.pathname.substr(1).split('/');
    if (path.indexOf("admin") > -1) {
        mangleFormForAdminUpdate();
        formState.stream = $(streams['admin-update']);
        formState.stream.addClass('current');
    } else if (path.indexOf("new") > -1) {
		$(function() { $("#new").click() });
	} else if (path.indexOf("update") > -1) {
		var uuid = path[path.indexOf("update")+1];
		if (uuid != null) {
			window.memberUuid = uuid;
		}
		$(function() { $("#update").click() });
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
		if (window.memberUuid != null) {
			obj['details_of_applicant']['uuid'] = window.memberUuid;
		}

		if (isTest) {
			return obj;
		} else {
			var self = this;
			$(this).attr("disabled", "disabled");
			$(this).text("Submitting...");
			$.ajax("/new_member", {
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
						$(self).removeAttr("disabled");
						$(self).text("Submit");
						return;
					}

					if (typeof data === "string") {
						alert("Unhandled error: " + data);
						$(self).removeAttr("disabled");
						$(self).text("Submit");
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
		i, ii, node, radios;
	
	$(form).find(".invalid").removeClass("invalid");
	for (i = 0, ii = res.length; i < ii; ++i) {
		node = $(res[i]);
        node.parents('.conditional').removeClass('invalid');

		if (node.hasClass('date') && !/^(0?[1-9]|[12][0-9]|3[01])\/(0?[1-9]|1[012])\/(19|20)\d\d$/.test(node.val())) {
			node.addClass('invalid');
			node.siblings('.invalid-msg').addClass('invalid');	
            node.parents('.conditional').addClass('invalid');
		} else if ((node.attr('type') == "checkbox") ? !node[0].checked : node.val() == "") {
		    node.addClass('invalid');
			node.parent().find('.invalid-msg').addClass('invalid');	
            node.parents('.conditional').addClass('invalid');
		} else if (node.attr('type') == 'radio' && node.attr('required')) {
            radios = $("input[name='" + node.attr('name') + "']");
            if (!radios.filter(":checked").length) {
                radios.addClass("invalid");
                $('.invalid-msg-' + node.attr('name')).addClass('invalid');
                radios.parents('.conditional').addClass('invalid');
            } else {
                radios.removeClass("invalid");
                $('.invalid-msg-' + node.attr('name')).removeClass('invalid');
                radios.parents('.conditional').removeClass('invalid');
            }
        }
	}
	return $(form).find(".invalid").length == 0;
}

function getFormData(form) {
	var obj = {}, i, ii, j, jj, parents, current,
		inputs = $(form)[0].elements, input;
	
	for (i = 0, ii = inputs.length; i < ii; ++i) {
		if ($(inputs[i]).hasClass('section')) {
			continue;
		}
		
		input = $(inputs[i]);
		if (input.attr('name') == null || input.attr('name') == "") {
			continue;
		}
		parents = input.parents('.section').toArray().reverse();
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
	
	$("input[required], select[required]").change(function() {
		validate(this.parentNode);
	});
	
	$("[id*=show\\:]").change(function() {
		var id = $(this).attr('id').split(":")[1];
		if (this.checked) {
			$("#" + id).css('display', '');
		} else {
			$("#" + id).css('display', 'none');
		}
	});
});
