function main(splash, args)
  assert(splash:go(args.url))
  assert(splash:wait(2))
  
  email_input = splash:select('input[name=email]')
  email_input:send_text("nv.nhat8002@gmail.com")
  
  pass_input = splash:select('input[name=pass]')
  pass_input:send_text("066099005844")
  splash:wait(1)
  
  button = splash:select('button[type="button"]')
  button:click()
  
  assert(splash:wait(5))
  
  pass_button = splash:select('a[role=button]')
  pass_button:click()
  
  assert(splash:wait(5))
  
  return {
    html = splash:html(),
    png = splash:png(),
    har = splash:har(),
  }
end