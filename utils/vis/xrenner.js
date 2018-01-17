function colorize(){
    // Count distinct groups:
    var items = {};
    i = 0;
    group_map={};
    $('[antecedent]').each(function(i) {
        items[$(this).attr('group')] = true;
    });
    i = 0;
    var result = new Array();
    for(var g in items)
    {
        result.push(g);
        group_map[g] = i;
        i++;
    }
    group_count = result.length;

    colors=get_fixed_colors(group_count);
    referents = $(".referent");
    for (referent in referents){
        if ($('[group='+$("#"+referents[referent].id).attr("group")+']').length > 1){
            $('[group='+$("#"+referents[referent].id).attr("group")+']').css("border-color",colors[group_map[parseInt($("#"+referents[referent].id).attr("group"))]]);
        }
    }

}


function get_fixed_colors(count){

colors = ["Red","RoyalBlue","ForestGreen","DarkMagenta","Brown","DarkTurquoise","Plum","Orange","Navy","Olive","LightSeaGreen","MediumSeaGreen","Aqua","Blue","BlueViolet","CadetBlue","Chartreuse","Chocolate","Coral","CornflowerBlue","Crimson","DarkBlue","DarkCyan","DarkGoldenRod","DarkGreen","DarkKhaki","DarkOliveGreen","DarkOrange","DarkOrchid","DarkRed","DarkSalmon","DarkSeaGreen","DarkSlateBlue","DarkSlateGray","DeepPink","DarkViolet","DeepSkyBlue","DimGray","DodgerBlue","FireBrick","Fuchsia","Gold","GoldenRod","Gray","Green","GreenYellow","HotPink","IndianRed","Indigo","Khaki","LawnGreen","LightBlue","LightCoral","LightGreen","LightPink","LightSalmon","LightSkyBlue","LightSlateGray","LightSteelBlue","Lime","LimeGreen","Magenta","Maroon","MediumAquaMarine","MediumBlue","MediumOrchid","MediumPurple","MediumSlateBlue","MediumSpringGreen","MediumTurquoise","MediumVioletRed","MidnightBlue","NavajoWhite","OliveDrab","OrangeRed","Orchid","PaleGreen","PaleTurquoise","PaleVioletRed","PeachPuff","Peru","Pink","PowderBlue","Purple","RebeccaPurple","RosyBrown","SaddleBrown","Salmon","SandyBrown","SeaGreen","Sienna","SkyBlue","SlateBlue","SlateGray","SpringGreen","SteelBlue","Tan","Teal","Thistle","Tomato","Turquoise","Violet","Wheat","Yellow"];
return colors.slice(0,count);

}

function highlight_group(group_id){

    if ($("[group="+group_id+"]").length > 1){
        $("[group="+group_id+"]").css("background-color","yellow");
    }
}

function unhighlight_group(group_id){

    if ($("[group="+group_id+"]").length > 1){
        $("[group="+group_id+"]").css("background-color","transparent");
    }
}

function load_example(val){
	$.get(val,
        function(returnedData){
            $('#plain_input').val(returnedData);
        }
	);
}

function set_lang_examples(val){

	eng_sources = 'English annotation examples taken from <a href="http://corpling.uis.georgetown.edu/gum">GUM</a>, raw data from <a href="https://en.wikinews.org/">Wikinews</a>, automatic English parses via the <a href="http://nlp.stanford.edu/software/lex-parser.shtml">Stanford Parser</a>.';
	deu_sources = 'German annotation examples taken from <a href="http://angcl.ling.uni-potsdam.de/resources/pcc.html">PCC</a>, raw data from the <a href="http://www.maz-online.de/">Märkische Allgemeine Zeitung</a>, automatic German parses using <a href="http://www.maltparser.org/">MaltParser</a>, tagging with <a href="http://www.cis.uni-muenchen.de/~schmid/tools/TreeTagger/">TreeTagger</a>, morphological analysis using <a href="http://www.cis.uni-muenchen.de/~schmid/tools/RFTagger/">RFTagger</a> and a nameless home-made compound analyzer.'
	cop_sources = 'Coptic annotation examples taken from <a href="http://data.copticscriptorium.org/urn:cts:copticLit:shenoute.fox.monbxh_204_216/">Not Because a Fox Barks / Shenoute</a>, automatic Coptic tagging using <a href="http://copticscriptorium.org/">Coptic Scriptorium</a> tools, parses using <a href="http://www.maltparser.org/">MaltParser</a>.'
	heb_sources = 'Hebrew annotation examples taken from the <a href="http://universaldependencies.org">Hebrew Universal Dependency Treebank</a>.'

	if (val =="deu"){
		document.getElementById("example").innerHTML= '				<option id="zossen_gold" value="zossen_gold.conll10.html">PCC_zossen (gold parse)</option>'+
				'<option id="zossen_auto" value="zossen_auto.conll10.html">PCC_zossen (auto parse)</option>'+
				'<option id="zossen_plain" value="zossen_plain.html">PCC_zossen (plain text)</option>';	
		document.getElementById("config_help").innerHTML = '        <img class="callout" src="img/callout.gif" />'+
	'Some language models allow multiple configurations to match different guidelines.'+
	'<br/>';				
		document.getElementById("example").value = "zossen_gold.conll10.html";
		document.getElementById("sources").innerHTML = deu_sources;
		document.getElementById("flavor").innerHTML= '<option id="tueba" value="tueba">TüBa-D/Z</option>';
		document.getElementById("plain_input").style.fontFamily = 'inherit';
	}
	else if (val =="cop"){
		document.getElementById("example").innerHTML= '				<option id="nbfb_gold" value="nbfb_gold.conll10.html">NBFB (gold parse)</option>'+
				'<option id="nbfb_auto" value="nbfb_auto.conll10.html">NBFB (auto parse)</option>'+
				'<option id="nbfb_plain" value="nbfb_plain.html">NBFB (plain text)</option>';	
		document.getElementById("config_help").innerHTML = '        <img class="callout" src="img/callout.gif" />'+
	'Some language models allow multiple configurations to match different guidelines.'+
	'<br/>';				
		document.getElementById("example").value = "nbfb_gold.conll10.html";
		document.getElementById("sources").innerHTML = cop_sources;
		document.getElementById("flavor").innerHTML= '<option id="scriptorium" value="scriptorium">Coptic Scriptorium</option>';
		document.getElementById("plain_input").style.fontFamily = 'antinoouRegular';
	}
	else if (val =="heb"){
		document.getElementById("example").innerHTML= '				<option id="knesset_gold" value="knesset_gold.conll10.html">Knesset (gold parse)</option>';	
		document.getElementById("config_help").innerHTML = '        <img class="callout" src="img/callout.gif" />'+
	'Some language models allow multiple configurations to match different guidelines.'+
	'<br/>';				
		document.getElementById("example").value = "knesset_gold.conll10.html";
		document.getElementById("sources").innerHTML = heb_sources;
		document.getElementById("flavor").innerHTML= '<option id="scriptorium" value="scriptorium">xrenner Hebrew</option>';
		document.getElementById("plain_input").style.fontFamily = 'inherit';
	}
	else { //load English examples by default
		document.getElementById("example").innerHTML= '		<option id="flag_gold" value="flag_gold.conll10.html">GUM_news_flag (gold parse)</option>' + 
'<option id="flag_auto" value="flag_auto.conll10.html">GUM_news_flag (auto parse)</option>' + 
'<option id="flag_plain" value="flag_plain.html">GUM_news_flag (plain text)</option>' + 
'<option id="test_hasa" value="test_hasa.conll10.html">test has-a</option>' + 
'<option id="test_dynamic_hasa" value="test_dynamic_hasa.conll10.html">test dynamic has-a</option>' + 
'<option id="test_isa" value="test_isa.conll10.html">test is-a</option>' + 
'<option id="test_entity_dep" value="test_entity_dep.conll10.html">test pron entity-dep</option>' + 
'<option id="test_chargram_morph" value="test_chargram_morph.conll10.html">test chargram morph</option>' + 
'<option id="test_cardinality" value="test_cardinality.conll10.html">test cardinality</option>' + 
'<option id="test_verb_event" value="test_verb_event.conll10.html">test verbal event</option>';
		document.getElementById("config_help").innerHTML = '        <img class="callout" src="img/callout.gif" />'+
	'Guideline configurations:'+
     '   <table id="flavor_tab">'+
	'	<tr><th>GUM</th><th>OntoNotes</th></tr></thead>'+
	'	<tr><td>no clauses in mention</td>'+
	'		<td>ignore single mentions</td></tr>'+
	'	<tr><td>mark cataphora</td>'+
	'		<td>wrap appositions</td></tr>'+
	'	<tr><td>wrap coordinations</td>'+
	'		<td>no indefinite anaphors</td></tr>'+
	'	</table>'+
	'<br/>';
				document.getElementById("example").value = "flag_gold.conll10.html";
				document.getElementById("sources").innerHTML = eng_sources;
				document.getElementById("flavor").innerHTML= '<option id="gum" value="GUM">GUM</option>'+
				'<option id="ontonotes" value="OntoNotes">OntoNotes</option>';
		document.getElementById("plain_input").style.fontFamily = 'inherit';				
	}
	load_example(document.getElementById("example").value);
	

}

function xrenner_analyze(){


	if (is_conll($("#plain_input").val())){
        if ((($("#plain_input").val().match(/[\r\n]/gm) || []).length > 500)) {
            //alert("You entered " + ($("#plain_input").val().match(/\n/g) || []).length + " lines. Please enter no more than 500 lines.");
            //return;
        }
        if ($("#plain_input").val().length > 15000){
            //alert("You entered " + $("#plain_input").val().length + " characters. Please enter no more than 15,000 characters in the conll format.");
            //return;
        }

		$('#status').html('Building discourse model <i class="fa fa-2x wobble-fix fa-spinner fa-spin fa-pulse"></i>');
		$.post('xrenner/xrenner_ajax.py', {
				conll: $("#plain_input").val(),
				model: $("#model").val(),
				flavor: $("#flavor").val()},
				function(returnedData){
					$("#analysis").html(returnedData);
					$('#status').html('Ready');
				}
		);
	}
	else {
        if ($("#plain_input").val().length > 700){
            alert("You entered " + $("#plain_input").val().length + " characters. Please enter no more than 700 characters.");
            //return;
        }
            //$("#plain_input").html(returnedData);
        $('#status').html('Parsing <i class="fa fa-2x wobble-fix fa-spinner fa-spin fa-pulse"></i>');
        $.post('xrenner/xrenner_ajax.py', {
        conll: $("#plain_input").val(),
        model: $("#model").val(),
        flavor: $("#flavor").val()},
            function(newData){
                    $("#plain_input").val(newData);
                    xrenner_analyze();
            }
        );
    }
}

$(document).ready(function() {
    $("#xrenner-main-contents").load("templates/demo.html");
    load_example('flag_gold.conll10.html');
});


function is_conll(input){
	lines = input.split("\n");

	for(i = 0; i < lines.length; i++){
		if (lines[i].length == 0){
				//space between sentences, ok
		}
		else if ((lines[i].match(/\t/g) || []).length==9){
			//9 tabs between 10 conll10 columns\\
		}
		else{
			return false;
		}
	}
	return true;
}


function load_content(section){

    $(".active").toggleClass("active");
    $("#"+section).toggleClass("active");
    if (section == "about"){
        $("#xrenner-main-contents").load("templates/about.html");
    }
    else if (section == "demo"){
        $("#xrenner-main-contents").load("templates/demo.html");
        load_example('flag_gold.conll10.html');
    }
    else if (section == "faq"){
        $("#xrenner-main-contents").load("templates/faq.html");
    }


}