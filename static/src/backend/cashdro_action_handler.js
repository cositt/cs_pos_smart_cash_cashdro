// Función global que será llamada desde la URL javascript:
window.cashdroValidateFromClient = function(host, user, pass, recordId) {
    console.log('🚀 Iniciando validación CashDro desde navegador');
    console.log('Host:', host, 'User:', user);
    
    const url = `https://${host}/Cashdro3WS/index.php?name=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}&operation=login`;
    
    console.log('📡 Conectando a:', url);
    
    fetch(url, {
        method: 'GET',
        mode: 'cors',
        credentials: 'omit'
    })
    .then(r => {
        console.log('✅ Respuesta HTTP:', r.status);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    })
    .then(data => {
        console.log('📊 Datos recibidos:', data);
        if (data.code === 1) {
            alert('✅ ÉXITO: Conexión exitosa con CashDro en ' + host);
        } else {
            alert('❌ Error: Respuesta inválida de CashDro (code=' + data.code + ')');
        }
    })
    .catch(err => {
        console.error('❌ Error:', err);
        alert('❌ Error: ' + err.message + '\n\nVerifica que:\n1. La IP ' + host + ' sea correcta\n2. Estés en la misma red que CashDro\n3. CashDro esté accesible desde tu navegador');
    });
};

console.log('✅ CashDro validator cargado globalmente');
