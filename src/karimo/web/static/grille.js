/* Enregistrement des notes sans rechargement de page.

   La grille se remplit debout dans une maison, d'une seule main : onze
   rechargements de page a la suite, chacun repositionnant le defilement,
   rendraient l'exercice penible. Ce fichier intercepte le tap, envoie la note
   en arriere-plan et met a jour l'affichage sur place.

   Amelioration progressive : sans JavaScript, les formulaires de la grille
   fonctionnent toujours, par POST et redirection. */

(function () {
  "use strict";

  var grille = document.querySelector(".grille");
  if (!grille || !window.fetch) return;

  var zoneScore = document.querySelector("[data-score]");
  var zoneAvertissement = document.querySelector("[data-avertissement]");

  function afficherScore(donnees) {
    if (zoneScore) {
      zoneScore.textContent = donnees.texte;
      if (donnees.verdict) {
        var accent = document.createElement("em");
        accent.textContent = donnees.verdict;
        zoneScore.appendChild(document.createTextNode(" "));
        zoneScore.appendChild(accent);
      }
    }
    if (zoneAvertissement) {
      zoneAvertissement.textContent = donnees.avertissement || "";
      zoneAvertissement.hidden = !donnees.avertissement;
    }
  }

  function marquer(formulaire, note) {
    formulaire.querySelectorAll(".bouton-note").forEach(function (bouton) {
      var choisi = note !== null && Number(bouton.value) === note;
      bouton.classList.toggle("choisi", choisi);
      bouton.setAttribute("aria-pressed", choisi ? "true" : "false");
    });
  }

  grille.addEventListener("click", function (evenement) {
    var bouton = evenement.target.closest(".bouton-note");
    if (!bouton) return;

    var formulaire = bouton.closest(".boutons-note");
    if (!formulaire) return;

    evenement.preventDefault();

    var corps = new FormData(formulaire);
    corps.set("note", bouton.value);
    formulaire.classList.add("en-cours");

    fetch(formulaire.action, {
      method: "POST",
      headers: { Accept: "application/json" },
      body: corps,
    })
      .then(function (reponse) {
        if (!reponse.ok) throw new Error(reponse.status);
        return reponse.json();
      })
      .then(function (donnees) {
        marquer(formulaire, donnees.note);
        afficherScore(donnees);
      })
      .catch(function () {
        /* Reseau ou serveur en defaut : on retombe sur l'envoi classique du
           formulaire, pour ne jamais perdre une note saisie en visite. */
        formulaire.submit();
      })
      .finally(function () {
        formulaire.classList.remove("en-cours");
      });
  });
})();
