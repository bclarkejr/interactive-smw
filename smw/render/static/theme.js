/* Theme resolution runs in the head, before body paint (spec §13.2). */
(function(){try{var t=localStorage.getItem('smw-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})();
document.addEventListener("DOMContentLoaded",function(){
  var b=document.getElementById("themeToggle"); if(!b) return;
  b.addEventListener("click",function(){
    var cur=document.documentElement.getAttribute("data-theme")
      ||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
    var next=cur==="dark"?"light":"dark";
    document.documentElement.setAttribute("data-theme",next);
    try{localStorage.setItem("smw-theme",next);}catch(e){}
  });
});
