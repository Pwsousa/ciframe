angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS) {
  var vm = this;
  vm.sequenciasFamosas = [];
  vm.minhaSequencia = {};
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech = "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  // Estado do catálogo
  vm.carregandoCatalogo = true;
  vm.erroCatalogo = "";

  // Formulário de cadastro de nova sequência
  vm.novaSequenciaNome = "";
  vm.novaSequenciaAcordes = ""; // ex.: "C G Am F"
  vm.mensagemErro = "";
  vm.mensagemSucesso = "";
  vm.mostrarCadastro = false;
  vm.cadastrando = false;

  var COR_LEGADO = '#2E1C74';
  var COR_COMUNIDADE = '#7B057E';

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  };

  var createChordsString = function(chords) {
    var str = "";
    for (var i = 0; i < chords.length; i++) {
      str = str.concat(chords[i].acorde, ',');
    }
    return str.substring(0, str.length - 1);
  };

  var parseAcordesString = function(str) {
    if (!str) {
      return [];
    }
    return str.split(/[\s,]+/).filter(function(a) { return a !== ''; });
  };

  vm.ehOriginal = function(sequencia) {
    return !!(sequencia && sequencia.legado);
  };

  // Preview dos acordes digitados, sem esperar o backend.
  vm.preview = [];
  vm.atualizarPreview = function() {
    vm.preview = parseAcordesString(vm.novaSequenciaAcordes).map(function(acorde) {
      return { acorde: acorde, cor: COR_COMUNIDADE };
    });
  };

  var mapearSequencia = function(seq) {
    var cor = seq.legado ? COR_LEGADO : COR_COMUNIDADE;
    return {
      id: seq.id,
      nome: seq.nome,
      legado: !!seq.legado,
      acordes: (seq.acordes || []).map(function(a) {
        return { acorde: a, cor: cor };
      })
    };
  };

  var carregarSequencias = function() {
    vm.carregandoCatalogo = true;
    vm.erroCatalogo = "";

    return $http.get('api/sequencias').then(function(resposta) {
      vm.sequenciasFamosas = (resposta.data || []).map(mapearSequencia);
      vm.carregandoCatalogo = false;
      return vm.sequenciasFamosas;
    }, function() {
      vm.carregandoCatalogo = false;
      vm.erroCatalogo = "Ops! Não foi possível carregar o catálogo de sequências.";
      return [];
    });
  };
  vm.carregarSequencias = carregarSequencias;

  var buscarSequencia = function(sequencia) {
    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequência...";
    vm.isSearching = true;
    vm.showSearchResultsCount = false;
    vm.musics = [];

    var searchString = "similares?sequencia=" +
      encodeURIComponent(createChordsString(sequencia.acordes));
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      searchString += "&generos=" + encodeURIComponent(vm.meuGenero);
    }

    $http.get(searchString).then(function(resposta) {
      vm.progressbar.complete();
      vm.esfigeSpeech = "Encontrei essas músicas";
      vm.isSearching = false;
      vm.showSearchResultsCount = true;
      vm.musics = resposta.data || [];
    }, function() {
      vm.progressbar.complete();
      vm.esfigeSpeech = "Ops! Algo deu errado na busca.";
      vm.isSearching = false;
      vm.showSearchResultsCount = false;
    });
  };

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    if (!vm.minhaSequencia.acordes || !vm.minhaSequencia.acordes.length) {
      return;
    }
    buscarSequencia(vm.minhaSequencia);
  };

  vm.cadastrarSequencia = function() {
    vm.mensagemErro = "";
    vm.mensagemSucesso = "";

    var acordes = parseAcordesString(vm.novaSequenciaAcordes);
    if (acordes.length < 2) {
      vm.mensagemErro = "Informe pelo menos 2 acordes.";
      return;
    }

    vm.cadastrando = true;
    $http.post('api/sequencias', {
      nome: vm.novaSequenciaNome,
      acordes: acordes
    }).then(function(resposta) {
      vm.cadastrando = false;
      vm.mensagemSucesso = "Sequência cadastrada com sucesso!";
      vm.novaSequenciaNome = "";
      vm.novaSequenciaAcordes = "";
      vm.mostrarCadastro = false;

      // Recarrega o catálogo e busca automaticamente a sequência criada.
      carregarSequencias().then(function(lista) {
        var criada = lista.filter(function(s) {
          return s.id === resposta.data.id;
        })[0];
        if (criada) {
          vm.pesquisarPorSequencia(criada);
        }
      });
    }, function(resposta) {
      vm.cadastrando = false;
      var dados = resposta.data || {};

      if (resposta.status === 409 && dados.sequencia) {
        vm.mensagemErro = "Essa sequência já está cadastrada.";
        carregarSequencias().then(function(lista) {
          var existente = lista.filter(function(s) {
            return s.id === dados.sequencia.id;
          })[0];
          if (existente) {
            vm.pesquisarPorSequencia(existente);
          }
        });
        return;
      }

      vm.mensagemErro = dados.erro || "Ops! Não foi possível cadastrar a sequência.";
    });
  };

  vm.limparPesquisa = function() {
    vm.minhaSequencia = {};
    vm.musics = [];
    vm.showSearchResultsCount = false;
  };

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({ scrollTop: $("#results").offset().top }, "slow");
  };

  // Inicializa carregando o catálogo real do backend.
  carregarSequencias();
});
