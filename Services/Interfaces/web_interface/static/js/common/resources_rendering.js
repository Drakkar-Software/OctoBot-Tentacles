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
                element.removeClass(hidden_class)
                const parentLink = element.parent("a");
                if (parentLink.attr("href") === ""){
                    parentLink.attr("href", data["url"]);
                }
            });
        }
    });
}

function handleDefaultImage(element, url){
    const imgSrc = element.attr("src");
    element.on("error",function () {
        if (imgSrc !== url){
            element.attr("src", url);
        }
    });
    if (((element[0].complete && element[0].naturalHeight === 0) && imgSrc !== url) || imgSrc.endsWith(currencyLoadingImageName)){
        element.attr("src", url);
    }
}

const fetchingCurrencies = [];
let currencyIdBySymbol = undefined;
let fetchedCurrencyIds = false;


function _useDefaultImage(element, currencyId){
    handleDefaultImage(element, currencyDefaultImage);
    fetchingCurrencies.splice(fetchingCurrencies.indexOf(currencyId), 1);
}


function fetchCurrencyImage(element, currencyId){
    if(element.parents("#AddCurrency-template-default").length > 0){
        // do not fetch images for default elements
        return;
    }
    if (fetchingCurrencies.indexOf(currencyId) === -1){
        fetchingCurrencies.push(currencyId);
        $.get({
            url: `https://api.coingecko.com/api/v3/coins/${currencyId}?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false`,
            dataType: "json",
            context: {element: element},
            success: function(data){
                if(isDefined(data["image"])){
                    const symbol = this.element.attr('symbol');
                    if(typeof symbol !== 'undefined'){
                        $(`img[symbol='${symbol.toLowerCase()}']`).each(function (){
                            if(!$(this).hasClass("default")){
                                $(this).attr("src", data["image"]["large"]);
                            }
                        });
                    }
                    const currencyId = this.element.attr('data-currency-id');
                    if(typeof currencyId !== 'undefined'){
                        $(`img[data-currency-id='${currencyId.toLowerCase()}']`).each(function (){
                            if(!$(this).hasClass("default")) {
                                $(this).attr("src", data["image"]["large"]);
                            }
                        });
                    }
                    fetchingCurrencies.splice(fetchingCurrencies.indexOf(currencyId), 1);
                }else{
                    _useDefaultImage(element, currencyId);
                }
            },
            error: function(result, status){
                window.console&&console.error(`Impossible to get the currency image for ${currencyId}: ${result.responseText} (${status})`);
                _useDefaultImage(element, currencyId);
            }
        });
    }
}

function fetchCurrencyIds(){
    currencyIdBySymbol = {};
    $.get({
        url: currencyListURL,
        dataType: "json",
        success: function (data) {
            $.each(data, function (_, element){
                currencyIdBySymbol[element["symbol"].toLowerCase()] = element["id"];
            });
            fetchedCurrencyIds = true;
            // refresh images
            handleDefaultImages();
        },
        error: function (result, status) {
            window.console && console.error(`Impossible to get currency list from coingecko.com: ${result.responseText} (${status})`);
        }
    });
}

function handleDefaultImages(){
    $(".currency-image").each(function () {
        const element = $(this);
        const imgSrc = element.attr("src");
        if (imgSrc === "" || imgSrc.endsWith(currencyLoadingImageName)) {
            if (element[0].hasAttribute("data-currency-id")) {
                fetchCurrencyImage(element, element.attr("data-currency-id").toLowerCase());
            }else if (element[0].hasAttribute("symbol")){
                const symbol = element.attr("symbol").toLowerCase();
                if (typeof currencyIdBySymbol === "undefined"){
                    fetchCurrencyIds();
                }else if (fetchedCurrencyIds){
                    if (currencyIdBySymbol.hasOwnProperty(symbol)){
                        fetchCurrencyImage(element, currencyIdBySymbol[symbol]);
                    }else{
                        handleDefaultImage(element, currencyDefaultImage);
                    }
                }
            }
        }
    });
}

const currencyLoadingImageName = "loading_currency.svg";
const currencyDefaultImage = `${window.location.protocol}//${window.location.host}/static/img/svg/default_currency.svg`;
const currencyListURL = `${window.location.protocol}//${window.location.host}/api/currency_list`;

// register error listeners as soon as possible
handleDefaultImages();

$(document).ready(function() {
    $(".markdown-content").each(function () {
        const element = $(this);
        element.html(markdown_to_html(element.text().trim()))
    });
    fetch_images();
});
