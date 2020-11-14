/*
 * Drakkar-Software OctoBot-Tentacles
 * Copyright (c) Drakkar-Software, All rights reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 3.0 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.
 */

const mardownConverter = new showdown.Converter();

function markdown_to_html(text) {
    return mardownConverter.makeHtml(text)
}

function fetch_images() {
    $(".product-logo").each(function () {
        const element = $(this);
        if(element.attr("src") === ""){
            $.get(element.attr("url"), function(data) {
                element.attr("src", data["image"]);
                const parentLink = element.parent("a");
                if (parentLink.attr("href") === ""){
                    parentLink.attr("href", data["url"]);
                }
            });
        }
    });
}

function handleDefaultImage(element, url){
    element.on("error",function () {
        if (element.attr("src") !== url){
            element.attr("src", url);
        }
    });
    if ((element[0].complete && element[0].naturalHeight === 0) && element.attr("src") !== url){
        element.attr("src", url);
    }
}

function handleDefaultImages(){
    $(".currency-image").each(function () {
        handleDefaultImage($(this), currencyDefaultImage);
    });
}

const currencyDefaultImage = `${window.location.protocol}//${window.location.host}/static/img/svg/default_currency.svg`;

// register error listeners as soon as possible
handleDefaultImages();

$(document).ready(function() {
    $(".markdown-content").each(function () {
        const element = $(this);
        element.html(markdown_to_html(element.text().trim()))
    });
    fetch_images();
});
