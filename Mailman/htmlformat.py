# Eventually could abstract down to HtmlItem, which outputs an arbitrary html
# object given start / end tags, valid options, and a value.
# Ug, objects shouldn't be adding their own newlines.  The next object should.


import string, types


# Format an arbitrary object.
def HTMLFormatObject(item, indent):
    try:
        if type(item) == type(''):
           return item
        if type(item) == type(2):
	    return `item`

	return item.Format(indent)
    except:
	return `item`
	

def CaseInsensitiveKeyedDict(d):
    result = {}
    for (k,v) in d.items():
	result[string.lower(k)] = v
    return result

# Given references to two dictionaries, copy the second dictionary into the
# first one.
def DictMerge(destination, fresh_dict):
    for (key, value) in fresh_dict.items():
	destination[key] = value

class Table:
    def __init__(self, **table_opts):
	self.cells = []
	self.cell_info = {}
	self.row_info = {}
	self.opts = table_opts

    def AddOptions(self, opts):
	DictMerge(self.opts, opts)

    # Sets all of the cells.  It writes over whatever cells you had there
    # previously.

    def SetAllCells(self, cells):
	self.cells = cells

    # Add a new blank row at the end
    def NewRow(self):
	self.cells.append([])

    # Add a new blank cell at the end
    def NewCell(self):
	self.cells[-1].append('')
	
    def AddRow(self, row):
	self.cells.append(row)

    def AddCell(self, cell):
	self.cells[-1].append(cell)

    def AddCellInfo(self, row, col, **kws):
	kws = CaseInsensitiveKeyedDict(kws)
	if not self.cell_info.has_key(row):
	    self.cell_info[row] = { col : kws }
	elif self.cell_info[row].has_key(col):
	    DictMerge(self.cell_info[row], kws)
	else:
	    self.cell_info[row][col] = kws
	
    def AddRowInfo(self, row, **kws):
	kws = CaseInsensitiveKeyedDict(kws)
	if not self.row_info.has_key(row):
	    self.row_info[row] = kws
	else:
	    DictMerge(self.row_info[row], kws)

    # What's the index for the row we just put in?
    def GetCurrentRowIndex(self):
	return len(self.cells)-1
    
    # What's the index for the col we just put in?
    def GetCurrentCellIndex(self):
	return len(self.cells[-1])-1

    def ExtractCellInfo(self, info):
	valid_mods = ['align', 'valign', 'nowrap', 'rowspan', 'colspan',
		      'bgcolor']
	output = ''

	for (key, val) in info.items():
	    if not key in valid_mods:
		continue
	    if key == 'nowrap':
		output = output + ' NOWRAP'
		continue
	    else:
		output = output + ' %s=%s' %(string.upper(key), val) 

	return output

    def ExtractRowInfo(self, info):
	valid_mods = ['align', 'valign', 'bgcolor']
	output = ''

	for (key, val) in info.items():
	    if not key in valid_mods:
		continue
	    output = output + ' %s=%s' %(string.upper(key), val) 

	return output

    def ExtractTableInfo(self, info):
	valid_mods = ['align', 'width', 'border', 'cellspacing', 'cellpadding',
		      'bgcolor']

	output = ''

	for (key, val) in info.items():
	    if not key in valid_mods:
		continue
	    if key == 'border' and val == None:
		output = output + ' BORDER'
		continue
	    else:	
		output = output + ' %s=%s' %(string.upper(key), val) 	

	return output

    def FormatCell(self, row, col, indent):
	try:
	    my_info = self.cell_info[row][col]
	except:
	    my_info = None

	output = '\n' + ' '*indent + '<td'
	if my_info:
	    output = output + self.ExtractCellInfo(my_info)
	item = self.cells[row][col]
	item_format = HTMLFormatObject(item, indent+4)
	output = '%s>%s</td>' % (output, item_format)
	return output

    def FormatRow(self, row, indent):
	try:
	    my_info = self.row_info[row]
	except:
	    my_info = None

	output = '\n' + ' '*indent + '<tr'
	if my_info:
	    output = output + self.ExtractRowInfo(my_info)
	output = output + '>'

	for i in range(len(self.cells[row])):
	    output = output + self.FormatCell(row, i, indent + 2)

	output = output + '\n' + ' '*indent + '</tr>'

	return output

    def Format(self, indent=0):
	output = '\n' + ' '*indent + '<table'
	output = output + self.ExtractTableInfo(self.opts)
	output = output + '>'

	for i in range(len(self.cells)):
	    output = output + self.FormatRow(i, indent + 2)

	output = output + '\n' + ' '*indent + '</table>\n'

	return output
	

class Link:
    def __init__(self, target, text):
	self.target = target
	self.text = text
    
    def Format(self, indent=0):
	return '<a href="%s">%s</a>' % (HTMLFormatObject(self.target, indent),
					HTMLFormatObject(self.text, indent))


class FontSize:
    def __init__(self, size, *items):
	self.items = list(items)
	self.size = size
    
    def Format(self, indent=0):
	output = '<font size="%s">' % self.size
	for item in self.items:
	    output = output + HTMLFormatObject(item, indent)
	output = output + '</font>'
	return output


class Container:
    def __init__(self, *items):
	if not items:
	    self.items = []
	else:
	    self.items = items

    def AddItem(self, obj):
	self.items.append(obj)

    def Format(self, indent=0):
	output = ''
	for item in self.items:
	    output = output + HTMLFormatObject(item, indent)
	return output

# My own standard document template.  YMMV.
# something more abstract would be more work to use...

class Document(Container):
    title = None

    def SetTitle(self, title):
	self.title = title

    def Format(self, indent=0):
	output = 'Content-type: text/html\n\n'
	spaces = ' ' * indent
	output = output + spaces
#	output = output + '<html>\n'
	if self.title:
	    output = '%s%s<TITLE>%s</TITLE>\n'  % (output, spaces,
						   self.title)
#	output = '%s%s<body>\n' % (output, ' '*indent)
	output = output + Container.Format(self, indent)
#	output = '%s\n%s</body>\n%s</html>\n' % (output, spaces, spaces)
	return output
    
class StdContainer(Container):
    def Format(self, indent=0):
	# If I don't start a new I ignore indent
	output = '<%s>' % self.tag
	output = output + Container.Format(self, indent)
	output = '%s</%s>' % (output, self.tag)
	return output	    


class Header(StdContainer):
    def __init__(self, num, *items):
	self.items = items
	self.tag = 'h%d' % num

class Address(StdContainer):
    tag = 'address'

class Underline(StdContainer):
    tag = 'u'
	
class Bold(StdContainer):
    tag = 'strong'  

class Italic(StdContainer):
    tag = 'em'

class Preformatted(StdContainer):
    tag = 'pre'

class Subscript(StdContainer):
    tag = 'sub'

class Superscript(StdContainer):
    tag = 'sup'

class Strikeout(StdContainer):
    tag = 'strike'

class Center(StdContainer):
    tag = 'center'

class Form(Container):
    def __init__(self, action='', method='POST', *items):
	apply(Container.__init__, (self,) +  items)
	self.action = action
	self.method = method

    def Format(self, indent=0):
	spaces = ' ' * indent
	output = '\n%s<FORM action="%s" method="%s">\n' % (spaces, self.action,
							 self.method)
	output = output + Container.Format(self, indent+2)
	output = '%s\n%s</FORM>\n' % (output, spaces)
	return output


class InputObj:
    def __init__(self, name, type, value, checked, **kws):
	self.name = name
	self.type = type
	self.value = `value`
	self.checked = checked
	self.kws = kws

    def Format(self, indent=0):
	output = '<INPUT name=%s type=%s value=%s' % (self.name, self.type,
						      self.value)
	
	for (key, val) in self.kws.items():
	    output = '%s %s=%s' % (output, key, val)

	if self.checked:
	    output = output + ' CHECKED'

	output = output + '>'
	return output

class SubmitButton(InputObj):
    def __init__(self, name, button_text):
	InputObj.__init__(self, name, "SUBMIT", button_text, checked=0)

class PasswordBox(InputObj):
    def __init__(self, name):
	InputObj.__init__(self, name, "PASSWORD", '', checked=0)

class TextBox(InputObj):
    def __init__(self, name, value='', size=10):
	InputObj.__init__(self, name, "TEXT", value, checked=0, size=size)

class TextArea:
    def __init__(self, name, text='', rows=None, cols=None, wrap='soft'):
	self.name = name
	self.text = text
	self.rows = rows
	self.cols = cols
	self.wrap = wrap

    def Format(self, indent=0):
	output = '<TEXTAREA NAME=%s' % self.name
	if self.rows:
	    output = output + ' ROWS=%s' % self.rows
	if self.cols:
	    output = output + ' COLS=%s' % self.cols
	if self.wrap:
	    output = output + ' WRAP=%s' % self.wrap
	output = output + '>%s</TEXTAREA>' % self.text
	return output


class RadioButton(InputObj):
    def __init__(self, name, value, checked=0, **kws):
	apply(InputObj.__init__, (self, name, 'RADIO', value, checked), kws)


class VerticalSpacer:
    def __init__(self, size=10):
	self.size = size
    def Format(self, indent=0):
	output = '<spacer type="vertical" height="%d">' % self.size
	return output 

class RadioButtonArray:
    def __init__(self, name, button_names, checked = None, horizontal=1):
	self.button_names = button_names
	self.horizontal = horizontal
	self.name = name
	self.checked = checked
	self.horizontal = horizontal

    def Format(self, indent=0):
	t = Table()
	items = []
	l = len(self.button_names)
  	for i in range(l):
	    if i == l:
		pref = ""
	    elif i == 0:
		pref = "&nbsp;"
	    else: pref = "&nbsp;&nbsp;&nbsp;&nbsp;"
  	    if self.checked == i:
  		items.append(pref + self.button_names[i])
  		items.append(RadioButton(self.name, i, 1))
  	    else:
  		items.append(pref + self.button_names[i])
  		items.append(RadioButton(self.name, i))
	if self.horizontal:
	    t.AddRow(items)
	else:
	    for item in items:
		t.AddRow([item])
	return t.Format(indent)

class UnorderedList(Container):
    def Format(self, indent=0):
	spaces = ' ' * indent
	output = '\n%s<ul>\n' % spaces
	for item in self.items:
	    output = output + '%s<li>%s\n' % (spaces, 
					      HTMLFormatObject(item, indent + 2))
	output = output + '%s</ul>\n' % spaces
	return output

class OrderedList(Container):
    def Format(self, indent=0):
	spaces = ' ' * indent
	output = '\n%s<ol>\n' % spaces
	for item in self.items:
	    output = output + '%s<li>%s\n' % (spaces, 
					      HTMLFormatObject(item, indent + 2))
	output = output + '%s</ol>\n' % spaces
	return output
	
