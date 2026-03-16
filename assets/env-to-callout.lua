function Div(div)
  if not quarto.doc.isFormat("pdf") then
    if div.classes:includes("solution") then
      div.classes = pandoc.List({"callout", "callout-note"})
      div.attributes["collapse"] = "true"
      div.attributes["title"] = "▸  הצג פתרון"
      return div
    elseif div.classes:includes("hint") then
      div.classes = pandoc.List({"callout", "callout-tip"})
      div.attributes["collapse"] = "true"
      div.attributes["title"] = "▸  רמז"
      return div
    end
  end
end
