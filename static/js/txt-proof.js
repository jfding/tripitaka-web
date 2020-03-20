/**
 * proofread.js
 * Date: 2018-9-19
 */

/** 切分字框相关代码 */
var showText = false;                     // 是否显示字框对应文字
var showOrder = false;                    // 是否显示字框对应序号
var showBlockBox = false;                 // 是否显示栏框切分坐标
var showColumnBox = false;                // 是否显示列框切分坐标
var offsetInSpan = null;                  // 当前选中范围开始位置
var currentSpan = [null];                 // $(当前span)，是否第一个

function getBlock(blockNo) {
  return $('#work-html .block').eq(blockNo - 1);
}

function getLine(blockNo, lineNo) {
  return getBlock(blockNo).find('.line').eq(lineNo - 1);
}

function getBlockNo(block) {
  return $('#work-html .block').index(block) + 1;
}

function getLineNo(line) {
  return line.parent().find('.line').index(line) + 1;
}

function findBestBoxes(offset, block_no, column_no, cmp) {
  var ret;
  var minNo = 10;
  $.cut.findCharsByLine(block_no, column_no, function (ch, box) {
    if (cmp(ch)) {
      if (minNo > Math.abs(offset + 1 - box.char_no)) {
        minNo = Math.abs(offset + 1 - box.char_no);
        ret = box;
      }
    }
  });
}

function getLineText($line) {
  var chars = [];
  var $span = $line.find('span');
  $span.each(function (i, el) {
    if ($(el).parent().prop('tagName') !== 'LI') {  // 忽略嵌套span，在新建行中粘贴其他行的内容产生的
      return;
    }
    var text = $(el).text().replace(/[\sYMN　]/g, '');  // 正字Y，模糊字M，*不明字占位
    if ($(el).hasClass('variant')) {
      chars = chars.concat(text.split(''));  // chars.push($(el).text());
    } else {
      var mb4Chars = ($(el).attr('utf8mb4') || '').split(',');
      var mb4Map = {}, order = 'a', c;
      mb4Chars.forEach(function (mb4Char) {
        if (mb4Char && text.indexOf(mb4Char) !== -1) {
          mb4Map[order] = mb4Char;
          text = text.replace(new RegExp(mb4Char, 'g'), order);
          order = String.fromCharCode(order.charCodeAt() + 1);
        }
      });
      text = text.split('').map(function (c) {
        return mb4Map[c] || c;
      });
      chars = chars.concat(text);
    }
  });
  return chars;
}

// 获取当前光标位置、当前选中高亮文本范围在当前span的开始位置
function getCursorPosition(element) {
  var caretOffset = 0;
  var doc = element.ownerDocument || element.document;
  var win = doc.defaultView || doc.parentWindow;
  var sel, range, preCaretRange;
  if (typeof win.getSelection !== 'undefined') {    // 谷歌、火狐
    sel = win.getSelection();
    if (sel.rangeCount > 0) {                       // 选中的区域
      range = sel.getRangeAt(0);
      caretOffset = range.startOffset;               // 获取选定区的开始点
      // preCaretRange = range.cloneRange();         // 克隆一个选中区域
      // preCaretRange.selectNodeContents(element);  // 设置选中区域的节点内容为当前节点
      // preCaretRange.setEnd(range.endContainer, range.endOffset);  // 重置选中区域的结束位置
      // caretOffset = preCaretRange.toString().length;
    }
  } else if ((sel = doc.selection) && sel.type !== 'Control') {    // IE
    range = sel.createRange();                          // 创建选定区域
    preCaretRange = doc.body.createTextRange();
    preCaretRange.moveToElementText(element);
    preCaretRange.setEndPoint('EndToEnd', range);
    caretOffset = preCaretRange.text.length;
  }
  return caretOffset;
}

// 点击文字区域时，高亮与文字对应的字框
function highlightBox($span, first, keyCode) {
  $span = $span || currentSpan[0];
  first = first || currentSpan[1];
  if (!$span)
    return;

  var $line = $span.parent();
  var line_no = getLineNo($line);
  var $block = $line.parent();
  var block_no = getBlockNo($block);
  var offset0 = parseInt($span.attr('offset'));
  offsetInSpan = first ? 0 : getCursorPosition($span[0]);
  offsetInSpan = offsetInSpan + (keyCode === 39 ? 1 : keyCode === 37 ? -1 : 0);
  offsetInSpan = offsetInSpan || 1;
  var offsetInLine = offsetInSpan + offset0;
  var ocrCursor = ($span.attr('base') || '')[offsetInSpan];
  var cmp1Cursor = ($span.attr('cmp1') || '')[offsetInSpan];
  var text = $span.text().replace(/\s/g, '');

  var i, chTmp, all, cmp_ch;

  // 根据文字序号寻找序号对应的字框
  var boxes = $.cut.findCharsByOffset(block_no, line_no, offsetInLine);
  // 根据文字的栏列号匹配到字框的列，然后根据文字精确匹配列中的字框
  if (!boxes.length)
    boxes = $.cut.findCharsByLine(block_no, line_no, function (ch) {
      return ch === ocrCursor || ch === cmp1Cursor;
    });
  // 行内多字能匹配时就取char_no位置最接近的，不亮显整列
  if (boxes.length > 1) {
    boxes[0] = findBestBoxes(offsetInLine, block_no, line_no, function (ch) {
      return ch === ocrCursor || ch === cmp1Cursor;
    }) || boxes[0];
  }
  // 用span任意字精确匹配
  if (!boxes.length) {
    cmp_ch = function (what, ch) {
      return !what || ch === what;
    };
    for (i = 0; i < text.length && !boxes.length; i++) {
      chTmp = cmp_ch.bind(null, text[i]);
      boxes = $.cut.findCharsByLine(block_no, line_no, chTmp);
    }
    if (boxes.length > 1) {
      boxes[0] = findBestBoxes(offsetInLine, block_no, line_no, chTmp) || boxes[0];
    } else if (!boxes.length) {
      boxes = $.cut.findCharsByLine(block_no, line_no, function (ch, box, i) {
        return i === offsetInLine;
      });
    }
  }
  // 当前行的所有字框
  if (!boxes.length) {
    boxes = $.cut.findCharsByLine(block_no, line_no);
  }
  $.cut.removeBandNumber(0, true);
  $.cut.state.focus = false;
  $.fn.mapKey.enabled = false;
  $.cut.data.block_no = block_no;
  $.cut.data.line_no = line_no;
  currentSpan = [$span, first];
  $.cut.switchCurrentBox((boxes[0] || {}).shape);
}

// 点击切分框
$.cut.onBoxChanged(function (char, box, reason) {
  if (reason === 'navigate' && char.column_no) {
    // 按字序号浮动亮显当前行的字框
    var $line = getLine(char.block_no, char.column_no);
    var text = getLineText($line);
    var all = $.cut.findCharsByLine(char.block_no, char.column_no);
    // 如果字框对应的文本行不是当前行，则更新相关设置
    var currentLineNo = getLineNo($('.current-span').parent());
    if (currentLineNo !== char.column_no) {
      var $firstSpan = $line.find('span:first-child');
      currentSpan = [$firstSpan, true];
    }
    $.cut.removeBandNumber(0, true);
    $.cut.showFloatingPanel(
        (showOrder || showText) ? all : [],
        function (char, index) {
          var no = showOrder ? char.char_no : '';
          var txt = !text[index] ? '？' : showText ? text[index] : '';
          // var cc = char.cc || 1;
          // var same = !char.ocr_txt || text[index] === char.ocr_txt || cc < 0.35;
          // return no + txt + (showText ? (same && (cc > 0.5 || cc < 0.35) ? '' : same ? '？' : char.ocr_txt) : '');
          return no + txt;
        },
        highlightBox
    );
    // 显示当前栏框
    if (showBlockBox) {
      $.cut.showBox('blockBox', window.blocks, all.length && all[0].char_id.split('c')[0]);
    }
    // 显示当前列框
    if (showColumnBox) {
      $.cut.showBox('columnBox', window.columns, all.length && all[0].char_id.split('c').slice(0, 2).join('c'));
    }
  }
});


/** 对话框相关代码 */
var $dlg = $("#pfread-dialog");

// 设置当前span和line
function setCurrent(span) {
  if (!$('.current-span').is(span)) {
    $('.current-span').removeClass('current-span');
    $('.current-line').removeClass('current-line');
    $(span).addClass('current-span').parent().addClass('current-line')
  }
}

// 单击同文、异文，设置当前span
$(document).on('click', '.same, .diff', function () {
  setCurrent($(this));
  highlightBox($(this));
});

// 双击异文，弹框提供选择
$(document).on('dblclick', '.diff', function (e) {
  e.stopPropagation();
  setCurrent($(this));
  // 设置当前异文
  $('.current-diff').removeClass('current-diff');
  $(this).addClass('current-diff');
  // 设置弹框文本
  var base = $(this).attr("base"), cmp1 = $(this).attr("cmp1"), cmp2 = $(this).attr("cmp2");
  $("#dlg-select").text($(this).text());
  $("#dlg-cmp1").text(cmp1).toggleClass('same-base', base === cmp1);
  $("#dlg-cmp2").text(cmp2).toggleClass('same-base', base === cmp2);
  $("#dlg-base").text(base).toggleClass('same-base', base === cmp2 || base === cmp2);
  // 设置弹框位置
  $dlg.show().offset({top: $(this).offset().top + 45, left: $(this).offset().left - 4});
  // 当弹框超出文字框时，向上弹出
  var o_t = $dlg.offset().top;
  var r_h = $(".html-text").height();
  var d_h = $('.dialog-abs').height();
  $('.dialog-abs').removeClass('dialog-common-t').addClass('dialog-common');
  if (o_t + d_h > r_h) {
    $dlg.offset({top: $(this).offset().top - 5 - $dlg.height()});
    $('.dialog-abs').removeClass('dialog-common').addClass('dialog-common-t');
  }
  // 当弹框右边出界时，向左移动
  var o_l = $dlg.offset().left;
  var d_r = $dlg[0].getBoundingClientRect().right;
  var r_w = $dlg.parent()[0].getBoundingClientRect().right;
  var offset = 0;
  if (d_r > r_w - 20) {
    offset = r_w - d_r - 20;
    $dlg.offset({left: o_l + offset});
  }
  // 设置弹框小箭头
  if (o_t + d_h > r_h) {
    var $mark = $dlg.find('.dlg-after');
    var ml = $mark.attr('last-left') || $mark.css('marginLeft');
    $mark.attr('last-left', ml).css('marginLeft', parseInt(ml) - offset);
  } else {
    var $mark = $dlg.find('.dlg-before');
    var ml = $mark.attr('last-left') || $mark.css('marginLeft');
    $mark.attr('last-left', ml).css('marginLeft', parseInt(ml) - offset);
  }
});

// 单击文本区的空白区域
$('.m-right').on('click', function (e) {
  if (!$dlg.is(e.target) && $dlg.has(e.target).length === 0) {
    $dlg.offset({top: 0, left: 0}).hide();
  }
});

// 滚动文本区滚动条
$('#work-html').on('scroll', function () {
  $dlg.offset({top: 0, left: 0}).hide();
});

// 点击异文选择框的各个选项
$('#pfread-dialog .option').on('click', function () {
  $('#dlg-select').text($(this).text());
  if (!$(this).text().length)
    $('.current-diff').text($(this).text()).addClass('selected');
});

// 对话框选择文本input发生修改
$("#dlg-select").on('DOMSubtreeModified', function () {
  $('.current-diff').text($(this).text()).addClass('selected');
  $('.current-diff').toggleClass('empty-place', $(this).text() === '');
});


/** 文本比对相关代码 */
function getWorkText() {
  return $.map($('#work-html .block'), function (block) {
    return $.map($(block).find('.line'), function (line) {
      return $.map($(line).find('span'), function (span) {
        return $(span).text();
      }).join("").trim();
    }).join("\n");
  }).join("\n\n");
}

function showTxt(txtId) {
  if (txtId === 'text-work') {
    $('#text-work textarea').val(getWorkText());
  }
  $('.sutra-text').addClass('hide');
  $('#' + txtId).removeClass('hide');
  resetHeight($('#' + txtId + ' textarea'));
}

function getText(txtType) {
  return $('#text-' + txtType).find('textarea').val();
}

function setDialogLabel(labels) {
  $('#dlg-items').html(labels.map(function (label, i) {
    var key = i ? 'cmp' + i : 'base';
    return `<dl class="item"><dt>${label}</dt><dd class="text option" id="dlg-${key}"></dd></dl>`;
  }).join(''));
}

// 查看文本
$('.btn-show-txt').on('click', function () {
  showTxt($(this).attr('data-id'));
});

// 重新比对
$('#btn-cmp-txt').on('click', function () {
  var base = $('.cmp-menu .base-txt :checked').val();
  if (!base)
    return showTips('提示', '请选择底本');
  var cmps = $.map($('.cmp-menu .cmp-txt :checked'), (item) => {
    if ($(item).val() && $(item).val() !== base)
      return $(item).val();
  });
  if (!cmps.length)
    return showTips('提示', '请选择校本');
  var texts = [base].concat(cmps).map((field) => getText(field));
  postApi('/page/text/diff', {data: {texts: texts}}, function (res) {
    $('#work-html .blocks').html(res['cmp_data']);
    showTxt('work-panel');
    setDialogLabel([base].concat(cmps).map((field) => textDict[field][2]));
    textKeys = [base].concat(cmps).map((field) => textDict[field][1]);
  });
});

function toggleWorkText(mode) {
  if (mode === 'raw') {
    showTxt('text-work');
    $('#btn-raw-txt').addClass('hide');
    $('#btn-html-txt').removeClass('hide');
  }
  if (mode === 'html') {
    showTxt('work-panel');
    $('#btn-raw-txt').removeClass('hide');
    $('#btn-html-txt').addClass('hide');
  }
}

// 进入工作文本
$('#btn-raw-txt').on('click', function () {
  toggleWorkText('raw');
});

// 回到工作面板
$('#btn-html-txt').on('click', function () {
  // 用工作文本替代底本与比对文本比对
  var texts = textKeys.map((txt) => getText(txt));
  texts[0] = $('#text-work textarea').val();
  var hints = $.map($('#work-html .selected'), function (i) {
    var lineNo = getLineNo($(i).parent());
    var blockNo = getBlockNo($(i).parent().parent());
    return {line_no: lineNo, block_no: blockNo, base: $(i).text(), cmp1: $(i).attr('cmp1'), offset: $(i).attr('offset')}
  });
  postApi('/page/text/diff', {data: {texts: texts, hints: hints}}, function (res) {
    $('#work-html .blocks').html(res['cmp_data']);
    toggleWorkText('html');
  });
});

$('.m-right textarea').on('input', function () {
  resetHeight($(this));
});


/** 存疑相关代码 */
// 点击存疑，弹出对话框
$('#save-doubt').on('click', function () {
  var txt = window.getSelection ? window.getSelection().toString() : '';
  if (!txt.length || !currentSpan[0]) {
    return showError('请先选择存疑文字', '');
  }
  $('#doubtModal .doubt_input').val(txt);
  $('#doubtModal .doubt_reason').val('');
  $('#doubtModal').modal();
});

// 存疑对话框，点击确认
$('#doubtModal .modal-confirm').on('click', function () {
  var reason = $('#doubtModal .doubt_reason').val().trim();
  if (reason.length <= 0)
    return showWarning('请填写存疑理由');
  var txt = $('#doubtModal .doubt_input').val().trim();
  var $span = $('.current-span');
  var offset0 = parseInt($span.attr('offset') || 0);
  var offsetInLine = offsetInSpan + offset0;
  var lineId = $span.parent().attr('id');
  if (!lineId)
    return showWarning('请先在文本区内选择文本');
  var line = "<tr class='char-list-tr' data='" + lineId + "' data-offset='" + offsetInLine +
      "'><td>" + lineId.replace(/[^0-9]/g, '') + "</td><td>" + offsetInLine +
      "</td><td>" + txt + "</td><td>" + reason +
      "</td><td class='del-doubt'><i class='icon-bin'></i></td></tr>";

  // 提交之后底部列表自动展开
  $('.doubt-list .toggle-tab').eq(0).click();
  $('.doubt-list .char-list-table.editable').append(line).removeClass('hidden');
  $('#toggle-arrow').removeClass('active');
  $('#doubtModal').modal('hide');
  markChanged();
});

// 切换存疑列表
$('.doubt-list .toggle-tab').on('click', function () {
  $(this).addClass('active').siblings().removeClass('active');
  var index = $('.doubt-list .toggle-tab').index($(this));
  $('.doubt-list .char-list-table').removeClass('active').eq(index).addClass('active');
});

// 展开或收缩存疑列表
$('#toggle-arrow').on('click', function () {
  $(this).toggleClass('active');
  $('.doubt-list .char-list-table.active').toggleClass('hidden');
});

// 删除存疑记录
$(document).on('click', '.del-doubt', function () {
  $(this).parent().remove();
});

// 记下当前span
$('.line > span').on('mousedown', function () {
  currentSpan[0] = $(this);
});

// 记下选中位置
$('.line > span').on('mouseup', function () {
  offsetInSpan = getCursorPosition(this);
});

$('.line > span').on('keydown', function (e) {
  var keyCode = e.keyCode || e.which;
  highlightBox($(this), false, keyCode);
});

function findSpanByOffset($li, offset) {
  var ret = [null, 0];
  $li.find('span').each(function (i, item) {
    var off = parseInt($(item).attr('offset'));
    if (i === 0) {
      ret = [$(this), offset]
    } else if (off <= offset) {
      ret = [$(this), offset - off];
    }
  });
  return ret;
}

function highlightInSpan(startNode, startOffset, endOffset) {
  var text = startNode.innerText;
  $(startNode).html(text.substring(0, startOffset) + '<b style="color: #f00">' +
      text.substring(startOffset, endOffset) + '</b>' + text.substring(endOffset));
  setTimeout(function () {
    $(startNode).text(text);
  }, 1300);
}

// 点击存疑列表，对应行blink
$(document).on('click', '.char-list-tr:not(.del-doubt)', function () {
  var $tr = $(this), id = $tr.attr('data'), $li = $('#' + id);
  var pos = findSpanByOffset($li, parseInt($tr.attr('data-offset')));
  var txt = $tr.find('td:nth-child(3)').text();
  $('#work-html').animate({scrollTop: $li.offset().top}, 100);
  if (pos[0]) {
    highlightInSpan(pos[0][0], pos[1], pos[1] + txt.length);
    setCurrent(pos[0]);
  }
});


/** 图文匹配相关代码 */

// 检查图文匹配
function checkMismatch(report, fromApi) {
  var mismatch = [];
  var lineCountMisMatch = '', ocrColumns = [];
  // 文本区每行的栏号和列号
  var lineNos = $('#work-html .line').map(function (i, line) {
    var blockNo = getBlockNo($(line).parent());
    var lineNo = getLineNo($(line));
    return {blockNo: blockNo, lineNo: lineNo};
  }).get();
  if (!fromApi) {
    return updateWideChars(lineNos, function () {
      checkMismatch(report, true);
    });
  }
  // ocrColumns: 从字框提取所有列（栏号和列号）
  $.cut.data.chars.forEach(function (c) {
    if (c.shape && c.column_no && (!c.class || c.class === 'char')) {
      var t = c.block_no + ',' + c.column_no;
      if (ocrColumns.indexOf(t) < 0) {
        ocrColumns.push(t);
      }
    }
  });
  // 先检查行列数是否匹配
  if (lineNos.length !== ocrColumns.length) {
    lineCountMisMatch = '总行数#文本' + lineNos.length + '行#图片' + ocrColumns.length + '行';
    mismatch.splice(0, 0, lineCountMisMatch);
  }
  var oldChanged = workChanged;
  lineNos.forEach(function (no) {
    var boxes = $.cut.findCharsByLine(no.blockNo, no.lineNo);
    var $line = getLine(no.blockNo, no.lineNo);
    var text = getLineText($line);
    var len = text.length;
    $line.toggleClass('mismatch', boxes.length !== len);
    if (boxes.length === len) {
      $line.removeAttr('mismatch');
      boxes.forEach(function (c, i) {
        (c._char || {}).txt = c.txt = text[i];
      });
    } else {
      $line.attr({
        mismatch: boxes.length + '!=' + len
            + ': ' + boxes.map(function (c) {
              return c.txt;
            }).join('') + ' -> ' + text.join('')
      });
    }
    if (boxes.length !== len) {
      mismatch.push('第' + no.lineNo + '行#文本 ' + len + '字#图片' + boxes.length + '字');
    }
  });
  $.cut.updateText && $.cut.updateText();
  workChanged = oldChanged;
  if (report) {
    if (mismatch.length) {
      var text = mismatch.map(function (t) {
        var ts = t.split('#');
        return '<li><span class="head">' + ts[0] + ':</span><span>' + ts[1] + '</span><span>' + ts[2] + '</span></li>';
      }).join('');
      text = '<ul class="match-tips">' + text + '</ul>';
      showTips("图文不匹配", text);
    } else {
      showTips("成功", "图文匹配", 1000);
    }
  }
}

// 调用后台API，根据文本行内容识别宽字符
function updateWideChars(lineNos, ended) {
  var texts = [];
  var oldChanged = workChanged;
  lineNos.forEach(function (no) {
    var $line = getLine(no.blockNo, no.lineNo);
    var spans = [];
    texts.push(spans);
    $line.find('span').each(function (i, el) {
      if ($(el).parent().prop('tagName') === 'LI') {  // 忽略嵌套span，在新建行中粘贴其他行的内容产生的
        var text = $(el).text().replace(/[\sYMN　]/g, '');  // 正字Y，模糊字M，*不明字占位
        spans.push(text);
      }
    });
  });
  postApi('/task/text/detect_chars', {data: {texts: texts}}, function (res) {
    lineNos.forEach(function (no, lineIdx) {
      var $line = getLine(no.blockNo, no.lineNo);
      $line.find('span').each(function (i, el) {
        if ($(el).parent().prop('tagName') === 'LI') {
          var mb4 = res.data[lineIdx][i];
          $(el).attr('utf8mb4', mb4);
        }
      });
    });
    workChanged = oldChanged;
    ended();
  }, ended);
}

$(document).ready(function () {
  checkMismatch(false);
});

$('#check-match').on('click', function () {
  checkMismatch(true);
});


/** 其它代码 */

// 粘贴时去掉格式
$(document).on('paste', 'span', function (e) {
  e.preventDefault();
  var text = e.originalEvent.clipboardData.getData('text/plain');
  document.execCommand('insertHTML', false, text);
});

// 自动保存修改
$('#work-html').on('DOMSubtreeModified', markChanged);

function markChanged() {
  workChanged++;
}

function autoSave(ended) {
  if (workChanged) {
    saveTask(false, null, function () {
      ended && ended();
    });
  } else {
    ended();
  }
}
