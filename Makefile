all: test

test:
	nosetests-2.7 -v -s -w lib/homnivore --with-gae --gae-application=gae
