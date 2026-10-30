const form = document.querySelector('#chat');
const prompt = document.querySelector('#prompt');
const model = document.querySelector('#model');
const provider = document.querySelector('#provider');
const messages = document.querySelector('#messages');
const status = document.querySelector('#status');
const button = form.querySelector('button');
const token = document.querySelector('meta[name="chat-token"]').content;
const history = [];
const models = {
  auto: [['auto', '자동 선택']],
  groq: [['openai/gpt-oss-120b', 'GPT-OSS 120B'], ['openai/gpt-oss-20b', 'GPT-OSS 20B']],
  openrouter: [['auto', '무료 모델 자동 선택']]
};
function updateModels() {
  model.replaceChildren(...models[provider.value].map(([value, label]) => new Option(label, value)));
}
provider.addEventListener('change', updateModels);
updateModels();

function addMessage(role, text) {
  const item = document.createElement('article');
  const label = document.createElement('strong');
  const body = document.createElement('p');
  label.textContent = role;
  body.textContent = text;
  item.append(label, body);
  messages.append(item);
  return body;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = prompt.value.trim();
  if (!text || button.disabled) return;
  const user = {role: 'user', content: text};
  addMessage('나', text);
  const answer = addMessage('AI', '');
  prompt.value = '';
  button.disabled = true;
  status.textContent = '응답 중…';
  let complete = false;
  let currentProvider = '';
  let notices = [];
  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Chat-Token': token},
      body: JSON.stringify({provider: provider.value, model: model.value, messages: [...history, user]})
    });
    if (!response.ok || !response.body) throw new Error(`요청 실패 (HTTP ${response.status})`);
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = '';
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += value;
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (!frame.startsWith('data: ')) continue;
        const event = JSON.parse(frame.slice(6));
        if (event.type === 'provider') { currentProvider = event.value; status.textContent = [...notices, `사용 중: ${currentProvider}`].join(' / '); }
        if (event.type === 'notice') { notices.push(event.value); status.textContent = notices.join(' / '); }
        if (event.type === 'text') answer.textContent += event.value;
        if (event.type === 'error') throw new Error(event.value);
        if (event.type === 'done') complete = true;
      }
    }
    if (!complete) throw new Error('응답이 완료되기 전에 연결이 종료되었습니다.');
    if (answer.textContent) history.push(user, {role: 'assistant', content: answer.textContent});
    status.textContent = [...notices, `완료: ${currentProvider}`].join(' / ');
  } catch (error) {
    status.textContent = `응답 중단: ${error.message}. 이 응답은 이후 대화에 포함되지 않습니다.`;
  } finally {
    button.disabled = false;
    prompt.focus();
  }
});
