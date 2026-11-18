/* Signature pads. Every [data-signature-pad] holds a canvas, a hidden input
   and a clear button; the drawing is written into the input when the form is
   submitted. The script is loaded once per pad and sets up the pads that are
   not ready yet. */
(function () {
  const MAX_RATIO = 2;

  function setUp(root) {
    const canvas = root.querySelector("canvas");
    const input = root.querySelector("input[type=hidden]");
    const pad = new SignaturePad(canvas);
    let width = null;

    function resize() {
      // Only a new width needs a new canvas; the drawing is kept.
      if (canvas.offsetWidth === width) {
        return;
      }
      width = canvas.offsetWidth;
      const ratio = Math.min(Math.max(window.devicePixelRatio || 1, 1), MAX_RATIO);
      const strokes = pad.toData();
      canvas.width = width * ratio;
      canvas.height = canvas.offsetHeight * ratio;
      canvas.getContext("2d").scale(ratio, ratio);
      pad.fromData(strokes);
    }

    // Follows every change of the layout, not only a resized window.
    new ResizeObserver(resize).observe(canvas);
    resize();
    root.querySelector("[data-signature-clear]").addEventListener("click", function () {
      pad.clear();
    });
    canvas.closest("form").addEventListener("submit", function () {
      input.value = pad.isEmpty() ? "" : pad.toDataURL();
    });
  }

  document.querySelectorAll("[data-signature-pad]:not([data-signature-ready])").forEach(function (root) {
    root.dataset.signatureReady = "true";
    setUp(root);
  });
})();
