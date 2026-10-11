/* Faux ECharts pour les tests : aucune dépendance au vrai fichier de tools/vendor/. */
window.echarts = {init: function () { return {setOption: function () {}, dispose: function () {}, resize: function () {}}; }};
